"""Обучение классификатора MNIST на данных из data/raw."""
import torch
from torch import nn


def model():
    return nn.Sequential(nn.Flatten(), nn.Linear(28 * 28, 128), nn.ReLU(), nn.Linear(128, 10))


if __name__ == "__main__":
    net = model()
    print(sum(p.numel() for p in net.parameters()), torch.__version__)
