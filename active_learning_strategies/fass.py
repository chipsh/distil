from .strategy import Strategy
import copy
import datetime
import numpy as np
import os
import subprocess
import sys
import time
import torch
import torch.backends.cudnn as cudnn
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable
from torch.utils.data import DataLoader
from matplotlib import pyplot as plt
import math
import random
from torch.distributions import Categorical
from .submodular import SubmodularFunction

class FASS(Strategy):

    def __init__(self, X, Y, unlabeled_x, net, handler, nclasses, args={}):
        
        if 'submod' in args:
            self.submod = args['submod']
        else:
            self.submod = 'facility_location'

        if 'selection_type' in args:
            self.selection_type = args['selection_type']
        else:
            self.selection_type = 'PerClass'
        super(FASS, self).__init__(X, Y, unlabeled_x, net, handler,nclasses, args)

    def select(self, budget):

        device = "cuda:0" if torch.cuda.is_available() else "cpu"

        submod_choices = ['facility_location', 'graph_cut', 'saturated_coverage', 'sum_redundancy', 'feature_based']
        if self.submod not in submod_choices:
            raise ValueError('Submodular function is invalid, Submodular functions can only be '+ str(submod_choices))
        selection_type = ['PerClass', 'Supervised']
        if self.selection_type not in selection_type:
            raise ValueError('Selection type is invalid, Selection type can only be '+ str(selection_type))

        curr_X_trn = self.unlabeled_x
        cached_state_dict = copy.deepcopy(self.model.state_dict())
        predicted_y = self.predict(curr_X_trn)  # Hypothesised Labels
        soft = self.predict_prob(curr_X_trn)    #Probabilities of each class

        entropy2 = Categorical(probs = soft).entropy()
        
        if 5*budget < entropy2.shape[0]:
            values,indices = entropy2.topk(5*budget)
        else:
            indices = [i for i in range(entropy2.shape[0])]    
        curr_X_trn = torch.from_numpy(curr_X_trn)

        #Handling image data, 3d to 2d
        if len(list(curr_X_trn.size())) == 3:
            curr_X_trn = torch.reshape(curr_X_trn, (curr_X_trn.shape[0], curr_X_trn.shape[1]*curr_X_trn.shape[2]))

        submodular = SubmodularFunction(device, curr_X_trn[indices], predicted_y[indices], self.model, curr_X_trn.shape[0], 32, True, self.submod, self.selection_type)
        dsf_idxs_flag_val = submodular.lazy_greedy_max(budget, cached_state_dict)

        #Mapping to original indices
        return_indices = []
        for val in dsf_idxs_flag_val:
            append_val = val
            return_indices.append(indices[append_val])
        return return_indices