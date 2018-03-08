#!/usr/bin/env python3

import time
from functools import reduce
import operator

import gym_duckietown
from gym_duckietown.envs import SimpleSimEnv

import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.autograd import Variable

from skimage import io

def initWeights(m):
    classname = m.__class__.__name__
    if classname.startswith('Conv'):
        nn.init.orthogonal(m.weight.data)
        m.bias.data.fill_(0)
    elif classname.find('Linear') != -1:
        nn.init.xavier_uniform(m.weight)
        m.bias.data.fill_(0)
    elif classname.find('BatchNorm') != -1:
        m.weight.data.normal_(1.0, 0.02)
        m.bias.data.fill_(0)

class Model(nn.Module):
    def __init__(self):
        super().__init__()

        self.conv1 = nn.Conv2d(3, 32, 8, stride=8)
        self.conv2 = nn.Conv2d(32, 32, 4, stride=1)
        self.conv3 = nn.Conv2d(32, 32, 4, stride=1)

        self.deconv1 = nn.ConvTranspose2d(32, 32, 4, stride=1)
        self.deconv2 = nn.ConvTranspose2d(32, 32, 4, stride=1)
        self.deconv3 = nn.ConvTranspose2d(32, 3, 8, stride=8)

        self.apply(initWeights)

    def forward(self, image):
        batch_size = image.size(0)

        x = image

        #print(x.size())

        x = self.conv1(x)
        x = F.leaky_relu(x)

        #print(x.size())

        x = self.conv2(x)
        x = F.leaky_relu(x)

        x = self.conv3(x)
        x = F.leaky_relu(x)

        #print(x.size())

        x = self.deconv1(x)
        x = F.leaky_relu(x)

        #print(x.size())

        x = self.deconv2(x)
        x = F.leaky_relu(x)

        x = self.deconv3(x)
        x = F.leaky_relu(x)

        #print(x.size())

        return x

    """
    def getValue(self, image):
        image = Variable(torch.from_numpy(image).float()).unsqueeze(0)
        x = self(image)
        return x.data[0]
    """

    def printInfo(self):
        modelSize = 0
        for p in self.parameters():
            pSize = reduce(operator.mul, p.size(), 1)
            modelSize += pSize
        print(str(self))
        print('Total model size: %d' % modelSize)

    def save(self, file_name):
        torch.save(self.state_dict(), file_name)

    def load(self, file_name):
        self.load_state_dict(torch.load(file_name))

def genData():
    img = env.reset().copy()
    seg = env._renderSeg().copy()

    img = img.transpose(2, 0, 1)
    seg = seg.transpose(2, 0, 1)

    return img, seg

def genBatch(batch_size=1):
    imgs = []
    segs = []

    for i in range(0, batch_size):
        img, seg = genData()
        imgs.append(img)
        segs.append(seg)

    imgs = np.stack(imgs)
    segs = np.stack(segs)

    return imgs, segs

def train(model, optimizer, image, target):
    # Zero the parameter gradients
    optimizer.zero_grad()

    # forward + backward + optimize
    output = model(image)

    loss = (output - target).norm(2).mean()
    loss.backward()
    optimizer.step()

    error = (output - target).abs().mean()

    return loss.data[0], error.data[0]

if __name__ == "__main__":
    env = SimpleSimEnv()
    env.reset()

    model = Model()
    model.printInfo()
    model.cuda()

    optimizer = optim.Adam(
        model.parameters(),
        lr=0.001
    )

    avg_error = 0

    for epoch in range(1, 1000000):
        startTime = time.time()
        images, targets = genBatch()
        images = Variable(torch.from_numpy(images).float()).cuda()
        targets = Variable(torch.from_numpy(targets).float()).cuda()
        genTime = int(1000 * (time.time() - startTime))

        startTime = time.time()
        loss, error = train(model, optimizer, images, targets)
        trainTime = int(1000 * (time.time() - startTime))

        avg_error = avg_error * 0.995 + 0.005 * error

        print('gen time: %d ms' % genTime)
        print('train time: %d ms' % trainTime)
        print('epoch %d, loss=%.3f, error=%.3f' % (epoch, loss, avg_error))


        if epoch % 500 == 0:
            img0 = images[0:1]
            out0 = model(img0)

            img0 = img0[0].clamp(0, 1).transpose(0, 2).transpose(0, 1).data
            out0 = out0[0].clamp(0, 1).transpose(0, 2).transpose(0, 1).data

            img0 = np.flip(img0, 0)
            out0 = np.flip(out0, 0)

            io.imsave('seg_img.png', img0)
            io.imsave('seg_out.png', out0)


        #if epoch % 100 == 0:
        #    model.save('trained_models/dist_model.pt')
