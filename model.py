import torch
import torch.nn as nn
import torch.nn.functional as F
from utils.blocks import bn, relu, ResBlock, BLD, Aspp, AsppPooling
import math


class DeepLabV3Plus(nn.Module):
    def __init__(self,
                 num_classes,
                 filters=[64, 64, 128, 128, 256],
                 res_n=[1, 2, 4, 4, 2]):
        super(DeepLabV3Plus, self).__init__()
        # full pre-activation
        self.conv1 = nn.Conv2d(3, 32, 7, 1, 3)
        self.block1 = nn.Sequential(ResBlock(32, 64, stride=2),
                                    ResBlock(64, 64, dilation=12))
        self.block2 = nn.Sequential(
            ResBlock(64, 128, stride=2),
            ResBlock(128, 128, dilation=12),
            ResBlock(128, 128),
        )
        self.block3 = nn.Sequential(
            ResBlock(128, 256, stride=2),
            ResBlock(256, 256),
            ResBlock(256, 256, dilation=6),
            ResBlock(256, 256),
            ResBlock(256, 256, dilation=12),
            ResBlock(256, 256),
            ResBlock(256, 256, dilation=18),
            ResBlock(256, 256),
            ResBlock(256, 256, dilation=30),
            ResBlock(256, 256),
        )

        self.aspp = Aspp(256, 256)
        self.low2high = ResBlock(128, 256)
        self.classifier = nn.Sequential(
            nn.Dropout(0.5),
            BLD(512, 256, 1),
            bn(256), relu,
            nn.Conv2d(256, num_classes, 1)
        )
        self.softmax = nn.Softmax(1)
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def forward(self, x):
        x = self.conv1(x)
        x = self.block1(x)
        x = self.block2(x)
        low_level_feat = x
        x = self.block3(x)
        high_level_feat = x
        high_level_feat = self.aspp(high_level_feat)
        high_level_feat = F.interpolate(high_level_feat,
                                        scale_factor=2,
                                        mode='bilinear',
                                        align_corners=True)
        low_level_feat = self.low2high(low_level_feat)
        final_feat = torch.cat([low_level_feat, high_level_feat], 1)
        final_feat = self.classifier(final_feat)
        final_feat = F.interpolate(final_feat,
                                   scale_factor=4,
                                   mode='bilinear',
                                   align_corners=True)
        return final_feat


class UNet(nn.Module):
    def __init__(self, num_classes):
        super(UNet, self).__init__()
        # full pre-activation
        self.conv1 = nn.Conv2d(3, 32, 7, 1, 3)
        self.block1 = nn.Sequential(BLD(32, 64, stride=2))
        self.block2 = nn.Sequential(
            BLD(64, 128, stride=2),
            ResBlock(128, 128),
            ResBlock(128, 128, dilation=12),
        )
        self.block3 = nn.Sequential(
            ResBlock(128, 256, stride=2),
            ResBlock(256, 256),
            ResBlock(256, 256, dilation=6),
            ResBlock(256, 256),
            ResBlock(256, 256, dilation=12),
            ResBlock(256, 256),
            ResBlock(256, 256, dilation=18),
            ResBlock(256, 256),
            ResBlock(256, 256, dilation=30),
            ResBlock(256, 128),
        )
        self.up_conv1 = nn.Sequential(
            ResBlock(128 * 3, 128 * 2),
            ResBlock(128 * 2, 128),
            nn.Dropout(0.5),
            BLD(128, 128, 1),
            bn(128),
            relu,
            nn.Conv2d(128, num_classes, 1),
        )
        self.aspp_pooling = AsppPooling(128, 128)
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def forward(self, x):
        x = self.conv1(x)
        x = self.block1(x)
        x = self.block2(x)
        feat2 = x
        x = self.block3(x)
        x = F.interpolate(
            x, scale_factor=2, mode='bilinear', align_corners=True)
        x = torch.cat([x, feat2, self.aspp_pooling(feat2)], 1)
        x = self.up_conv1(x)
        x = F.interpolate(x,
                          scale_factor=4,
                          mode='bilinear',
                          align_corners=True)
        return x


if __name__ == "__main__":
    a = torch.ones([2, 3, 224, 224])
    print(UNet(8)(a).shape)
    print(DeepLabV3Plus(8)(a).shape)
