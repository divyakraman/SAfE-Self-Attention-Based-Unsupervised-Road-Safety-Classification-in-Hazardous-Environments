import numpy as np
import matplotlib.pyplot as plt
import glob
#import imageio
import torch
import torch.nn.functional as F
import torch.optim as optim
import os
from PIL import Image
import os.path as osp
from dataset.weather import weatherFogDataSet
from torch.utils import data
from torch.autograd import Variable
import torch.nn as nn
from sklearn.metrics import confusion_matrix

os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID" 
os.environ["CUDA_VISIBLE_DEVICES"]="1"

dtype = torch.cuda.FloatTensor #GPU
 
data_dir = 'path to folder containing dataset'
data_list = 'path to list of training images, txt file'
batch_size = 1
num_steps = ADD #num_images
input_size_target = 'w,h'
eval_set = 'test' 
num_workers = 4
 

IMG_MEAN = np.array((104.00698793, 116.66876762, 122.67891434), dtype=np.float32)

w, h = map(int, input_size_target.split(','))
input_size_target = (w, h)

targetloader = data.DataLoader(cityscapesFogDataSet(data_dir, data_list, max_iters=num_steps * batch_size, crop_size=input_size_target, 
    scale=False, mean=IMG_MEAN, set = eval_set), batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True)

targetloader_iter = enumerate(targetloader)
num_classes = 1

colors = [ [128,64,128],
]
#ignoring void class

interp_target = nn.Upsample(size=(input_size_target[1], input_size_target[0]), mode='bilinear')

def fast_hist(a,b,n):
    k = (a>=0) & (a<n)
    return np.bincount(n*a[k].astype(int)+b[k], minlength=n**2).reshape(n,n)

def per_class_iu(hist):
    return np.diag(hist)/(hist.sum(1)+hist.sum(0)-np.diag(hist))

def prob_2_entropy(prob):
    """ convert probabilistic prediction maps to weighted self-information maps
    """
    n, c, h, w = prob.size()
    return -torch.mul(prob, torch.log2(prob + 1e-30)) / np.log2(c)


model = torch.load('snapshots/stage3.pth', map_location='cpu')

model = model.cuda()

hist = np.zeros((num_classes,num_classes))

conf_matrix = np.array([[0,0],[0,0]])

for iteration in range(0,num_steps):
    _, batch = targetloader_iter.__next__()
    images, labels, name = batch
    images = Variable(images).cuda()
    
    out, out_attn = model(images) 

    pred = interp_target(out)
    pred = F.sigmoid(pred)
    del out
    pred = pred.detach()
    pred = pred.cpu()
    pred = pred.numpy()
    pred = pred[0,0,:,:]
    pred[pred>=0.5]=1
    pred[pred<0.5]=0
    pred = pred.astype(np.int)
    
    #print(np.max(pred), np.min(pred))
    
    labels = labels.cpu()
    labels = labels.numpy()
    labels1 = labels
    del labels
    labels1[labels1!=0]=1
    labels1 = labels1[0,:,:]
    labels1 = labels1+1
    labels1[labels1==2]=0
    labels1 = labels1.astype(np.int)

    
    conf_matrix = conf_matrix + confusion_matrix(np.ravel(labels1),np.ravel(pred))
    
    tn,fp,fn,tp = conf_matrix.ravel() #if 1:positive, 0:negative
    iou = tp/(tp+fp+fn)
    print('===> IoU: ' + str(round(np.nanmean(iou*100), 2)))
    


    
    torch.cuda.empty_cache() #clear cached memory
    print(iteration)

mIoUs = per_class_iu(hist)

conf_matrix = conf_matrix/(num_steps*w*h)



tn,fp,fn,tp = conf_matrix.ravel() #if 1:positive, 0:negative
#tp,fn,fp,tn = conf_matrix.ravel() 
precision = tp/(tp+fp)
recall = tp/(tp+fn)
f1 = (2*precision*recall)/(precision+recall)
iou = tp/(tp+fp+fn)

print('===> Precision: ' + str(round(np.nanmean(precision)*100, 4)))
print('===> Recall: ' + str(round(np.nanmean(recall)*100, 4))) #=Accuracy
print('===> F1: ' + str(round(np.nanmean(f1)*100, 4)))
print('===> IoU: ' + str(round(np.nanmean(iou)*100, 4)))




