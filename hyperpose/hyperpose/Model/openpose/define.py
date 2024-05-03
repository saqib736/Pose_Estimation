import numpy as np
from enum import Enum
#specialized for coco
class CocoPart(Enum):
    Nose = 0
    Neck = 1
    LShoulder = 2
    RShoulder = 3
    LElbow = 4
    RElbow = 5
    LWrist = 6
    RWrist = 7
    LHip = 8
    RHip = 9
    LKnee = 10
    RKnee = 11
    LAnkle = 12
    RAnkle = 13
    Background = 14

CocoLimb=list(zip([0, 1, 1, 2, 4, 3, 5, 1, 1,  8, 10,  9, 11],
                  [1, 2, 3, 4, 6, 5, 7, 8, 9, 10, 12, 11, 13]))

CocoColor = [[255, 0, 0], [255, 85, 0], [255, 170, 0], [255, 255, 0], [170, 255, 0], [85, 255, 0], [0, 255, 0],
              [0, 255, 85], [0, 255, 170], [0, 255, 255], [0, 170, 255], [0, 85, 255], [0, 0, 255], [85, 0, 255]]

def get_coco_flip_list():
    flip_list=[]
    for part_idx,part in enumerate(CocoPart):
        #shoulder flip
        if(part==CocoPart.RShoulder):
            flip_list.append(CocoPart.LShoulder.value)
        elif(part==CocoPart.LShoulder):
            flip_list.append(CocoPart.RShoulder.value)
        #elbow flip
        elif(part==CocoPart.RElbow):
            flip_list.append(CocoPart.LElbow.value)
        elif(part==CocoPart.LElbow):
            flip_list.append(CocoPart.RElbow.value)
        #wrist flip
        elif(part==CocoPart.RWrist):
            flip_list.append(CocoPart.LWrist.value)
        elif(part==CocoPart.LWrist):
            flip_list.append(CocoPart.RWrist.value)
        #hip flip
        elif(part==CocoPart.RHip):
            flip_list.append(CocoPart.LHip.value)
        elif(part==CocoPart.LHip):
            flip_list.append(CocoPart.RHip.value)
        #knee flip
        elif(part==CocoPart.RKnee):
            flip_list.append(CocoPart.LKnee.value)
        elif(part==CocoPart.LKnee):
            flip_list.append(CocoPart.RKnee.value)
        #ankle flip
        elif(part==CocoPart.RAnkle):
            flip_list.append(CocoPart.LAnkle.value)
        elif(part==CocoPart.LAnkle):
            flip_list.append(CocoPart.RAnkle.value)
        #others
        else:
            flip_list.append(part.value)
    return flip_list

Coco_flip_list=get_coco_flip_list()

#specialized for mpii
class MpiiPart(Enum):
    Headtop=0
    Neck=1
    RShoulder=2
    RElbow=3
    RWrist=4
    LShoulder=5
    LElbow=6
    LWrist=7
    RHip=8
    RKnee=9
    RAnkle=10
    LHip=11
    LKnee=12
    LAnkle=13
    Center=14
    Background=15

MpiiLimb=list(zip([0, 1, 2, 3, 1, 5, 6, 1,  14,  8, 9,  14, 11, 12],
                  [1, 2, 3, 4, 5, 6, 7, 14,  8,  9, 10, 11, 12, 13]))

MpiiColor = [[255, 0, 0], [255, 85, 0], [255, 170, 0], [255, 255, 0], [170, 255, 0], [85, 255, 0], [0, 255, 0],
              [0, 255, 85], [0, 255, 170], [0, 255, 255], [0, 170, 255], [0, 85, 255], [0, 0, 255], [85, 0, 255],
              [170, 0, 255], [255, 0, 255], [255, 0, 170], [255, 0, 85]]

def get_mpii_flip_list():
    flip_list=[]
    for part_idx,part in enumerate(MpiiPart):
        #shoulder flip
        if(part==MpiiPart.RShoulder):
            flip_list.append(MpiiPart.LShoulder.value)
        elif(part==MpiiPart.LShoulder):
            flip_list.append(MpiiPart.RShoulder.value)
        #elbow flip
        elif(part==MpiiPart.RElbow):
            flip_list.append(MpiiPart.LElbow.value)
        elif(part==MpiiPart.LElbow):
            flip_list.append(MpiiPart.RElbow.value)
        #wrist flip
        elif(part==MpiiPart.RWrist):
            flip_list.append(MpiiPart.LWrist.value)
        elif(part==MpiiPart.LWrist):
            flip_list.append(MpiiPart.RWrist.value)
        #hip flip
        elif(part==MpiiPart.RHip):
            flip_list.append(MpiiPart.LHip.value)
        elif(part==MpiiPart.LHip):
            flip_list.append(MpiiPart.RHip.value)
        #knee flip
        elif(part==MpiiPart.RKnee):
            flip_list.append(MpiiPart.LKnee.value)
        elif(part==MpiiPart.LKnee):
            flip_list.append(MpiiPart.RKnee.value)
        #ankle flip
        elif(part==MpiiPart.RAnkle):
            flip_list.append(MpiiPart.LAnkle.value)
        elif(part==MpiiPart.LAnkle):
            flip_list.append(MpiiPart.RAnkle.value)
        #others
        else:
            flip_list.append(part.value)
    return flip_list

Mpii_flip_list=get_mpii_flip_list()