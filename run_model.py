import json
import numpy as np
from IPython import embed
import os
from collections import OrderedDict
import pandas as pd
from warnings import warn

def sigm_tf(x):
    return 1./(1 + np.exp(-1 * x))

def sigm(x):
    return 2./(1 + np.exp(-2 * x)) - 1

class QuaLiKizNDNN():
    def __init__(self, nn_dict):
        """ General ND fully-connected multilayer perceptron neural network

        Initialize this class using a nn_dict. This dict is usually read 
        directly from JSON, and has a specific structure. Generate this JSON
        file using the supplied function in QuaLiKiz-Tensorflow
        """
        parsed = {}
        # Read and parse the json. E.g. put arrays in arrays and the rest in a dict
        for name, value in nn_dict.items():
            if value.__class__ == list:
                parsed[name] = np.array(value)
            else:
                parsed[name] = dict(value)
        # These variables do not depend on the amount of layers in the NN
        for name in ['prescale_bias', 'prescale_factor', 'feature_min',
                     'feature_max', 'feature_names', 'target_names']:
            setattr(self, name, pd.Series(parsed.pop(name), name=name))
        self.layers = []
        # Now find out the amount of layers in our NN, and save the weigths and biases
        for ii in range(1, len(parsed)+1):
            try:
                name = 'layer' + str(ii)
                weight = parsed.pop(name + '/weights/Variable:0')
                bias = parsed.pop(name + '/biases/Variable:0')
                activation = sigm
                self.layers.append(QuaLiKizNDNN.NNLayer(weight, bias, activation))
            except KeyError:
                # This name does not exist in the JSON,
                # so our previously read layer was the one
                break
                
        assert not any(parsed), 'nn_dict not fully parsed!'

    def apply_layers(self, input):
        """ Apply all NN layers to the given input

        The given input has to be array-like, but can be of size 1
        """
        for layer in self.layers:
            input = layer.apply(input)
        return input


    class NNLayer():
        """ A single (hidden) NN layer
        A hidden NN layer is just does

        output = activation(weight * input + bias)

        Where weight is generally a matrix; output, input and bias a vector
        and activation a (sigmoid) function.
        """
        def __init__(self, weight, bias, activation):
            self.weight = weight
            self.bias = bias
            self.activation = activation 

        def apply(self, input):
            preactivation = np.matmul(input, self.weight) + self.bias
            result = self.activation(preactivation)
            return result

        def shape(self):
            return self.weight.shape

        def __str__(self):
            return ('NNLayer shape ' + str(self.shape()))

    def get_output(self, **kwargs):
        """ Calculate the output given a specific input

        This function accepts inputs in the form of a dict with
        as keys the name of the specific input variable (usually
        at least the feature_names) and as values 1xN same-length
        arrays.
        """
        nn_input = pd.DataFrame()
        # Read and scale the inputs
        for name in self.feature_names:
            try:
                value = kwargs.pop(name)
                nn_input[name] = self.prescale_factor[name] * value + self.prescale_bias[name]
            except KeyError as e:
                raise Exception('NN needs \'' + name + '\' as input')

        output = pd.DataFrame()
        # Apply all NN layers an re-scale the outputs
        for name in self.target_names:
            nn_output = (np.squeeze(self.apply_layers(nn_input)) - self.prescale_bias[name]) / self.prescale_factor[name]
            output[name] = nn_output

        if any(kwargs):
            for name in kwargs:
                print(name)
                warn('input dict not fully parsed! Did not use ' + name)
        return output

    @classmethod
    def from_json(cls, json_file):
        with open(json_file) as file_:
            dict_ = json.load(file_)
        nn = QuaLiKizNDNN(dict_)
        return nn

if __name__ == '__main__':
    # Test the function
    root = os.path.dirname(os.path.realpath(__file__))
    nn = QuaLiKizNDNN.from_json(os.path.join(root, 'nn.json'))
    scann = 24
    input = pd.DataFrame()
    input['Ati'] = np.array(np.linspace(2,13, scann))
    input['Ti_Te']  = np.full_like(input['Ati'], 1.)
    input['Zeffx']  = np.full_like(input['Ati'], 1.)
    input['An']  = np.full_like(input['Ati'], 2.)
    input['Ate']  = np.full_like(input['Ati'], 5.)
    input['qx'] = np.full_like(input['Ati'], 0.660156)
    input['smag']  = np.full_like(input['Ati'], 0.399902)
    input['Nustar']  = np.full_like(input['Ati'], 0.009995)
    input['x']  = np.full_like(input['Ati'], 0.449951)
    fluxes = nn.get_output(**input)
    embed()
