import torch
import torch.nn as nn
import torch.nn.functional as F
from utils.modules.nn import Aspp, Swish, CNS, EmptyLayer, MbBlock, ResBlock
from utils.modules.backbones import BasicModel, EfficientNet, ResNet
import math


class DeepLabV3Plus(BasicModel):
    def __init__(self, num_classes):
        super(DeepLabV3Plus, self).__init__()
        # self.backbone = EfficientNet(2)
        # self.backbone.block5 = nn.Sequential(
        #     MbBlock(
        #         self.backbone.width[5],
        #         self.backbone.width[6],
        #         5,
        #         dilation=2,
        #         reps=self.backbone.depth[-1],
        #     ),
        #     MbBlock(
        #         self.backbone.width[6],
        #         self.backbone.width[6],
        #         5,
        #         dilation=4,
        #         reps=self.backbone.depth[-1],
        #     ),
        #     MbBlock(
        #         self.backbone.width[6],
        #         self.backbone.width[7],
        #         3,
        #         dilation=8,
        #         reps=self.backbone.depth[-1],
        #     ),
        # )
        self.backbone = ResNet()
        self.backbone.block5 = nn.Sequential(
            ResBlock(512, 1024, dilation=2, reps=2), 
            ResBlock(1024, 1024, dilation=4, reps=1), 
            ResBlock(1024, 1024, dilation=8, reps=1),             
        )
        self.aspp = Aspp(1024, 256, [6, 12, 18])
        self.cls_conv = nn.Sequential(
            nn.Conv2d(256 + 128,
                      num_classes,
                      3,
                      padding=1))
        # init weight and bias
        self.init()

    def forward(self, x):
        x = self.backbone.block1(x)
        x = self.backbone.block2(x)
        low = x
        x = self.backbone.block3(x)
        x = self.backbone.block4(x)
        x = self.backbone.block5(x)
        x = self.aspp(x)
        x = F.interpolate(x,
                          scale_factor=4,
                          mode='bilinear',
                          align_corners=True)
        x = torch.cat([x, low], 1)
        x = self.cls_conv(x)
        x = F.interpolate(x,
                          scale_factor=4,
                          mode='bilinear',
                          align_corners=True)
        return x


class UNet(BasicModel):
    def __init__(self, num_classes):
        super(UNet, self).__init__()
        self.backbone = EfficientNet(4)
        self.backbone.block5 = EmptyLayer()
        self.up_conv4 = CNS(160, 56)
        self.up_conv3 = CNS(112, 32)
        self.up_conv2 = CNS(64, 24)
        self.cls_conv = nn.Conv2d(48, num_classes, 3, padding=1)
        # init weight and bias
        self.init()

    def forward(self, x):
        x = self.backbone.block1(x)
        x1 = x
        x = self.backbone.block2(x)
        x2 = x
        x = self.backbone.block3(x)
        x3 = x
        x = self.backbone.block4(x)
        x = self.up_conv4(x)
        x = F.interpolate(x,
                          scale_factor=2,
                          mode='bilinear',
                          align_corners=True)
        x = torch.cat([x, x3], 1)
        x = self.up_conv3(x)
        x = F.interpolate(x,
                          scale_factor=2,
                          mode='bilinear',
                          align_corners=True)
        x = torch.cat([x, x2], 1)
        x = self.up_conv2(x)
        x = F.interpolate(x,
                          scale_factor=2,
                          mode='bilinear',
                          align_corners=True)
        x = torch.cat([x, x1], 1)
        x = F.interpolate(x,
                          scale_factor=2,
                          mode='bilinear',
                          align_corners=True)
        x = self.cls_conv(x)
        return x


if __name__ == "__main__":
    a = torch.ones([2, 3, 224, 224])
    model = DeepLabV3Plus(30)
    o = model(a)
    model.train()
    print(o.shape)
    o.mean().backward()
