import numpy as np
import torch
from PIL import Image

from detection.anchors import build_anchors_maps
from detection.box_coding import encode_boxes
from detection.box_utils import boxes_area


class Resize(object):
    def __init__(self, size, interpolation=Image.BILINEAR):
        self.size = size
        self.interpolation = interpolation

    def __call__(self, input):
        return resize(input, size=self.size, interpolation=self.interpolation)


class RandomResize(object):
    def __init__(self, min_max_size, interpolation=Image.BILINEAR):
        self.min_max_size = min_max_size
        self.interpolation = interpolation

    def __call__(self, input):
        size = np.random.randint(self.min_max_size[0], self.min_max_size[1] + 1)

        return resize(input, size=size, interpolation=self.interpolation)


class RandomCrop(object):
    def __init__(self, size, min_size=8**2):
        self.size = size
        self.min_size = min_size

    def __call__(self, input):
        image = input['image']

        w, h = image.size
        t = np.random.randint(0, h - self.size + 1)
        l = np.random.randint(0, w - self.size + 1)

        return crop(input, (t, l), (self.size, self.size), min_size=self.min_size)


class RandomFlipLeftRight(object):
    def __call__(self, input):
        if np.random.random() > 0.5:
            input = flip_left_right(input)

        return input


class BuildLabels(object):
    def __init__(self, anchors, min_iou, max_iou):
        self.anchors = anchors
        self.min_iou = min_iou
        self.max_iou = max_iou

    def __call__(self, input):
        image, dets = input['image'], (input['class_ids'], input['boxes'])

        _, h, w = image.size()
        anchor_maps = build_anchors_maps((h, w), self.anchors)
        maps = encode_boxes(dets, anchor_maps, min_iou=self.min_iou, max_iou=self.max_iou)

        return image, maps


def resize(input, size, interpolation=Image.BILINEAR):
    image, boxes = input['image'], input['boxes']

    w, h = image.size
    scale = size / min(w, h)
    w, h = round(w * scale), round(h * scale)

    image = image.resize((w, h), interpolation)
    boxes = boxes * scale

    return {
        **input,
        'image': image,
        'boxes': boxes,
    }


def flip_left_right(input):
    image, boxes = input['image'], input['boxes']

    image = image.transpose(Image.FLIP_LEFT_RIGHT)
    w, _ = image.size
    boxes[:, 1], boxes[:, 3] = w - boxes[:, 3], w - boxes[:, 1]

    return {
        **input,
        'image': image,
    }


def denormalize(tensor, mean, std, inplace=False):
    if not inplace:
        tensor = tensor.clone()

    mean = torch.as_tensor(mean, dtype=torch.float32, device=tensor.device)
    std = torch.as_tensor(std, dtype=torch.float32, device=tensor.device)
    tensor.mul_(std[:, None, None]).add_(mean[:, None, None])

    return tensor


# TODO: test min-size removal
def crop(input, tl, hw, min_size):
    image, class_ids, boxes = input['image'], input['class_ids'], input['boxes']

    t, l = tl
    h, w = hw

    image = image.crop((l, t, l + w, t + h))

    boxes[:, [0, 2]] -= t
    boxes[:, [1, 3]] -= l
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clamp(0, h)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clamp(0, w)

    keep = boxes_area(boxes) >= min_size
    class_ids = class_ids[keep]
    boxes = boxes[keep]

    return {
        **input,
        'image': image,
        'class_ids': class_ids,
        'boxes': boxes,
    }
