import json
import numpy as np
from IPython import embed
import os
from collections import OrderedDict
import pandas as pd
from warnings import warn
from numba import jit,float64

def sigm_tf(x):
    return 1./(1 + np.exp(-1 * x))

#def sigm(x):
#    return 2./(1 + np.exp(-2 * x)) - 1

class QuaLiKizMultiNN():
    def __init__(self, nns):
        self._nns = nns
        feature_names = nns[0]
        for nn in self._nns:
            if len(nn.target_names) == 1:
                name = nn.target_names[0]
            else:
                NotImplementedError('Multitarget not implemented yet')
            if np.all(nn.feature_names.ne(feature_names)):
                Exception('Supplied NNs have different feature names')
        if np.any(self.feature_min > self.feature_max):
            raise Exception('Feature min > feature max')

    @property
    def target_names(self):
        targets = []
        for nn in self._nns:
            targets.extend(list(nn.target_names))
        return targets

    def get_output(self, target, **kwargs):
        for nn in self._nns:
            if [target] == list(nn.target_names):
                result = nn.get_output(**kwargs)
                break
            elif target in nn.target_names.values:
                NotImplementedError('Multitarget not implemented yet')
        return result

    def get_outputs(self, **kwargs):
        results = pd.DataFrame()
        feature_max = -np.inf
        feature_min = np.inf
        for nn in self._nns:
            if len(nn.target_names) == 1:
                #name = nn.target_names[0]
                out = nn.get_output(**kwargs)
                results[out.columns] = nn.get_output(**kwargs)
            elif target in nn.target_names.values:
                NotImplementedError('Multitarget not implemented yet')

        return results

    @property
    def target_names(self):
        target_names = []
        for nn in self._nns:
            target_names.extend(nn.target_names)
        return list(set(target_names))

    @property
    def feature_names(self):
        return self._nns[0].feature_names

    @property
    def feature_max(self):
        feature_max = pd.Series(np.full_like(self._nns[0].feature_max, np.inf),
                                index=self._nns[0].feature_max.index)
        for nn in self._nns:
            feature_max = nn.feature_max.combine(feature_max, min)
        return feature_max

    @property
    def feature_min(self):
        feature_min = pd.Series(np.full_like(self._nns[0].feature_min, -np.inf),
                                index=self._nns[0].feature_min.index)
        for nn in self._nns:
            feature_min = nn.feature_min.combine(feature_min, max)
        return feature_min

class QuaLiKizComboNN():
    def __init__(self, target_name, nns, combo_func):
        self._nns = nns
        feature_names = nns[0]
        for nn in self._nns:
            if np.all(nn.feature_names.ne(feature_names)):
                Exception('Supplied NNs have different feature names')
        if np.any(self.feature_min > self.feature_max):
            raise Exception('Feature min > feature max')

        self._combo_func = combo_func
        self._target_name = target_name

    def get_output(self, **kwargs):
        output = pd.DataFrame()
        #output1 = self._nn1.get_output(**kwargs).values
        #output2 = self._nn2.get_output(**kwargs).values
        #output[self._target_name] = np.squeeze(self._combo_func(output1, output2))
        output[self._target_name] = np.squeeze(self._combo_func(*[nn.get_output(**kwargs).as_matrix() for nn in self._nns]))
        return output

    @property
    def target_names(self):
        return [self._target_name]

    @property
    def feature_names(self):
        return self._nns[0].feature_names

    @property
    def feature_max(self):
        feature_max = pd.Series(np.full_like(self._nns[0].feature_max, np.inf),
                                index=self._nns[0].feature_max.index)
        for nn in self._nns:
            feature_max = nn.feature_max.combine(feature_max, min)
        return feature_max

    @property
    def feature_min(self):
        feature_min = pd.Series(np.full_like(self._nns[0].feature_min, -np.inf),
                                index=self._nns[0].feature_min.index)
        for nn in self._nns:
            feature_min = nn.feature_min.combine(feature_min, max)
        return feature_min

class QuaLiKizDuoNN():
    def __init__(self, target_name, nn1, nn2, combo_func):
        self._nn1 = nn1
        self._nn2 = nn2
        if np.any(self.feature_min > self.feature_max):
            raise Exception('Feature min > feature max')
        if np.all(nn1.feature_names.ne(nn2.feature_names)):
            Exception('Supplied NNs have different feature names')
        self._combo_func = combo_func
        self._target_name = target_name

    def get_output(self, **kwargs):
        output = pd.DataFrame()
        output1 = self._nn1.get_output(**kwargs).values
        output2 = self._nn2.get_output(**kwargs).values
        output[self._target_name] = np.squeeze(self._combo_func(output1, output2))
        return output

    @property
    def target_names(self):
        return [self._target_name]

    @property
    def feature_names(self):
        return self._nn1.feature_names

    @property
    def feature_max(self):
        return self._nn1.feature_max.combine(self._nn2.feature_max, min)

    @property
    def feature_min(self):
        return self._nn1.feature_min.combine(self._nn2.feature_min, max)

class QuaLiKizNDNN():
    def __init__(self, nn_dict, target_names_mask=None):
        """ General ND fully-connected multilayer perceptron neural network

        Initialize this class using a nn_dict. This dict is usually read
        directly from JSON, and has a specific structure. Generate this JSON
        file using the supplied function in QuaLiKiz-Tensorflow
        """
        parsed = {}
        # Read and parse the json. E.g. put arrays in arrays and the rest in a dict
        for name, value in nn_dict.items():
            if name == 'hidden_activation' or name == 'output_activation':
                parsed[name] = value
            elif value.__class__ == list:
                parsed[name] = np.array(value)
            else:
                parsed[name] = dict(value)
        # These variables do not depend on the amount of layers in the NN
        setattr(self, '_feature_names', pd.Series(parsed.pop('feature_names')))
        setattr(self, '_target_names', pd.Series(parsed.pop('target_names')))
        setattr(self, '_target_prescale_factors', pd.Series(parsed['prescale_factor'])[self._target_names])
        setattr(self, '_feature_prescale_factors', pd.Series(parsed.pop('prescale_factor'))[self._feature_names])
        setattr(self, '_target_prescale_biases', pd.Series(parsed['prescale_bias'])[self._target_names])
        setattr(self, '_feature_prescale_biases', pd.Series(parsed.pop('prescale_bias'))[self._feature_names])
        for name in ['feature_min', 'feature_max', 'target_min', 'target_max']:
            setattr(self, '_' + name, pd.Series(parsed.pop(name), name=name))
        self.layers = []
        # Now find out the amount of layers in our NN, and save the weigths and biases
        activations = parsed['hidden_activation'] + [parsed['output_activation']]
        for ii in range(1, len(activations) + 1):
            try:
                name = 'layer' + str(ii)
                weight = parsed.pop(name + '/weights/Variable:0')
                bias = parsed.pop(name + '/biases/Variable:0')
                activation = activations.pop(0)
                if activation == 'tanh':
                    act = np.tanh
                elif activation == 'relu':
                    act = _act_relu
                elif activation == 'none':
                    act = _act_none
                self.layers.append(QuaLiKizNDNN.NNLayer(weight, bias, act))
            except KeyError:
                # This name does not exist in the JSON,
                # so our previously read layer was the output layer
                break
        if len(activations) == 0:
            del parsed['hidden_activation']
            del parsed['output_activation']
        try:
            self._clip_bounds = parsed['_metadata']['clip_bounds']
        except KeyError:
            self._clip_bounds = False

        self._target_names_mask = target_names_mask
        # Ignore metadata
        try:
            self._metadata = parsed.pop('_metadata')
        except KeyError:
            pass
        if any(parsed):
            warn('nn_dict not fully parsed! ' + str(parsed))

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
            #self.weight = weight
            #self.bias = bias
            #self.activation = activation
            #@jit(float64[:,:](float64[:,:]), nopython=True)
            #def _apply_layer(input):
            #    preactivation = np.dot(input, weight) + bias
            #    result = activation(preactivation)
            #    return result
            self.apply = lambda input: activation(np.dot(input, weight) + bias)
            #_create_apply(weight, bias, activation)

        #def apply(self, input):
        #    preactivation = np.dot(input, self.weight) + self.bias
        #    result = self.activation(preactivation)
        #    return result

        def shape(self):
            return self.weight.shape

        def __str__(self):
            return ('NNLayer shape ' + str(self.shape()))

    # 7.09 ms ± 11.4 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)
    # 4.75 ms ± 44.7 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)
    #@jit(nopython=True, debug=True)

    def get_output(self, input, clip_low=True, clip_high=True, low_bound=None, high_bound=None, safe=True):
        """ Calculate the output given a specific input

        This function accepts inputs in the form of a dict with
        as keys the name of the specific input variable (usually
        at least the feature_names) and as values 1xN same-length
        arrays.
        """
        # ~500 us
        # Read and scale the inputs
        #for name in self.feature_names:
        #    try:
        #        value = input.pop(name)
        #        nn_input[name] = value
        #    except KeyError as e:
        #        raise Exception('NN needs \'' + name + '\' as input')
        if safe:
            nn_input = input[self._feature_names]
        else:
            nn_input = input

        #nn_input = self._feature_prescale_factors.values[np.newaxis, :] * nn_input + self._feature_prescale_biases.values
        # 10.6 µs ± 503 ns per loop (mean ± std. dev. of 7 runs, 100000 loops each)
        nn_input = _prescale(nn_input.values,
                  self._feature_prescale_factors.values,
                  self._feature_prescale_biases.values)

        # Apply all NN layers an re-scale the outputs
        # 702 µs ± 5.66 µs per loop (mean ± std. dev. of 7 runs, 1000 loops each)
        output = {}
        for name in self._target_names:
            nn_output = (np.squeeze(self.apply_layers(nn_input)) - self._target_prescale_biases[name]) / self._target_prescale_factors[name]
            output[name] = nn_output
        output = pd.DataFrame(output)

        # 2.6 µs ± 32.5 ns per loop (mean ± std. dev. of 7 runs, 100000 loops each)
        if clip_low:
            for name, column in output.items():
                if low_bound is None:
                    low_bound = self._target_min[name]
                output[output < low_bound] = low_bound
        if clip_high:
            for name, column in output.items():
                if high_bound is None:
                    high_bound = self._target_max[name]
                output[output > high_bound] = high_bound

        #if any(kwargs):
        #    for name in kwargs:
        #        warn('input dict not fully parsed! Did not use ' + name)

        if self._target_names_mask is not None:
            output.columns = self._target_names_mask
        return output

    @classmethod
    def from_json(cls, json_file, **kwargs):
        with open(json_file) as file_:
            dict_ = json.load(file_)
        nn = QuaLiKizNDNN(dict_, **kwargs)
        return nn

    @property
    def l2_norm(self):
        l2_norm = 0
        for layer in self.layers:
            l2_norm += np.sum(np.square(layer.weight))
        l2_norm /= 2
        return l2_norm

    @property
    def l1_norm(self):
        l1_norm = 0
        for layer in self.layers:
            l1_norm += np.sum(np.abs(layer.weight))
        return l1_norm

#@jit(float64[:,:](float64[:,:], float64[:], float64[:]), nopython=True)
def _prescale(nn_input, factors, biases):
    return np.atleast_2d(factors) * nn_input + biases
#    #return factors[np.newaxis, :] * nn_input + biases
#
#@jit(float64[:,:](float64[:,:]), nopython=True)
def _act_none(x):
    return x
#
#@jit(float64[:,:](float64[:,:]), nopython=True)
def _act_relu(x):
    return x * (x > 0)
#
##@jit(float64[:,:](float64[:,:], float64[:,:,:]), nopython=True)
##def _apply_layers(self, input, layers):
##    for layer in layers:
##        input = layer.apply(input)
##    return input
#
#def _create_apply(weight, bias, activation):
#    #self.weight = weight
#    #self.bias = bias
#    #self.activation = activation
#    #if activation is None:
#    #    @jit(float64[:,:](float64[:,:]), nopython=True)
#    #    def _apply_layer(input):
#    #        preactivation = np.dot(input, weight) + bias
#    #        result = preactivation
#    #        return result
#    #else:
#    @jit(float64[:,:](float64[:,:]), nopython=True)
#    def _apply_layer(input):
#        preactivation = np.dot(input, weight) + bias
#        result = activation(preactivation)
#        return result
#
#    return _apply_layer

if __name__ == '__main__':
    # Test the function
    root = os.path.dirname(os.path.realpath(__file__))
    #nn1 = QuaLiKizNDNN.from_json(os.path.join(root, 'nn_efe_GB.json'))
    #nn2 = QuaLiKizNDNN.from_json(os.path.join(root, 'nn_efi_GB.json'))
    #nn3 = QuaLiKizDuoNN('nn_eftot_GB', nn1, nn2, lambda x, y: x + y)
    #nn = QuaLiKizMultiNN([nn1, nn2])
    nn = QuaLiKizNDNN.from_json('nn.json')
    scann = 100
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
    input = input[nn._feature_names]
    fluxes = nn.get_output(input, safe=False)
    print(fluxes)
    embed()
