from __future__ import division
import re
from itertools import product
from IPython import embed
import pandas as pd
import numpy as np
import gc

particle_vars = [u'pf', u'df', u'vt', u'vr', u'vc']
heat_vars = [u'ef']
momentum_vars = [u'vf']
store_format = 'table'

#'vti_GB', 'dfi_GB', 'vci_GB',
#       'pfi_GB', 'efi_GB',
#       
#       'efe_GB', 'vce_GB', 'pfe_GB',
#       'vte_GB', 'dfe_GB'
             #'chie', 'ven', 'ver', 'vec']
def regime_filter(data, leq, less):
    bool = pd.Series(np.full(len(data), True, dtype='bool'), index=data.index)
    bool &= (data['efe_GB'] < less) & (data['efi_GB'] < less)
    bool &= (data['efe_GB'] >= leq) & (data['efi_GB'] >= leq)
    data = data.loc[bool]
    return data

def stability_filter(data):
    for col in data.columns:
        splitted = re.compile('(?=.*)(.)(|ITG|ETG|TEM)_(GB|SI|cm)').split(col)
        if splitted[0] not in heat_vars + particle_vars + momentum_vars:
            print('skipping {!s}'.format(col))
            continue
        if splitted[2] == 'TEM':
            gam_filter = 'tem'
        elif splitted[2] == 'ITG':
            gam_filter = 'itg'
        elif splitted[2] == 'ETG':
            gam_filter = 'elec'
        elif splitted[0] in heat_vars and splitted[1] == 'e':
            gam_filter = 'multi'
        else:
            gam_filter = 'ion'

        pre = len(data[col])
        if gam_filter == 'ion':
            data[col] = data[col].loc[data['gam_leq_GB'] != 0]
        elif gam_filter == 'elec':
            data[col] = data[col].loc[data['gam_great_GB'] != 0]
        elif gam_filter == 'multi':
            data[col] = data[col].loc[(data['gam_leq_GB'] != 0) | (data['gam_great_GB'] != 0)]
        elif gam_filter == 'tem':
            data[col] = data[col].loc[data['TEM']]
        elif gam_filter == 'itg':
            data[col] = data[col].loc[data['ITG']]
        print('{:.2f}% of sane {!s:<9} points unstable at {!s:<5} scale'.format(np.sum(~data[col].isnull()) / pre * 100, col, gam_filter))
    return data

def filter_negative(data):
    bool = pd.Series(np.full(len(data), True, dtype='bool'), index=data.index)
    for col in data.columns:
        splitted = re.compile('(?=.*)(.)(|ITG|ETG|TEM)_(GB|SI|cm)').split(col)
        if splitted[0] in heat_vars:
            bool &= (data[col] >= 0)
        elif splitted[0] in particle_vars:
            pass
    return bool

def filter_ck(data, bound):
    return (np.abs(data['cki']) < bound) & (np.abs(data['cke']) < bound)

def filter_totsep(data, septot_factor, startlen=None):
    if startlen is None:
        startlen = len(data)
    bool = pd.Series(np.full(len(data), True, dtype='bool'), index=data.index)
    for type, spec in product(particle_vars + heat_vars, ['i', 'e']):
        totname = type + spec + '_GB'
        if totname != 'vre_GB' and totname != 'vri_GB':
            if type in particle_vars or spec == 'i': # no ETG
                seps = ['ITG', 'TEM']
            else: # All modes
                seps = ['ETG', 'ITG', 'TEM']
            for sep in seps:
                sepname = type + spec + sep + '_GB'
                #sepflux += data[sepname]
                bool &= np.abs(data[sepname]) <= septot_factor * np.abs(data[totname])

            print('After filter {!s:<6} {!s:<6} {:.2f}% left'.format('septot', totname, 100*np.sum(bool)/startlen))
    return bool

def filter_ambipolar(data, bound):
    return (data['absambi'] < bound) & (data['absambi'] > 1/bound)

def filter_femtoflux(data, bound):
    fluxes = [col for col in data if len(re.compile('(?=.*)(.)(|ITG|ETG|TEM)_(GB|SI|cm)').split(col)) > 1 if re.compile('(?=.*)(.)(|ITG|ETG|TEM)_(GB|SI|cm)').split(col)[0] in particle_vars + heat_vars + momentum_vars]
    absflux = data[fluxes].abs()
    return ~((absflux < bound) & (absflux != 0)).any(axis=1)

def sanity_filter(data, ck_bound, septot_factor, ambi_bound, femto_bound, startlen=None):
    if startlen is None:
        startlen = len(data)
    # Throw away point if negative heat flux
    data = data.loc[filter_negative(data)]
    print('After filter {!s:<13} {:.2f}% left'.format('negative', 100*len(data)/startlen))
    gc.collect()


    # Throw away point if cke or cki too high
    data = data.loc[filter_ck(data, ck_bound)]
    print('After filter {!s:<13} {:.2f}% left'.format('ck', 100*len(data)/startlen))
    gc.collect()

    # Throw away point if sep flux is way higher than tot flux
    data = data.loc[filter_totsep(data, septot_factor, startlen=startlen)]
    print('After filter {!s:<13} {:.2f}% left'.format('septot', 100*len(data)/startlen))
    gc.collect()

    data = data.loc[filter_ambipolar(data, ambi_bound)]
    print('After filter {!s:<13} {:.2f}% left'.format('ambipolar', 100*len(data)/startlen))
    gc.collect()

    data = data.loc[filter_femtoflux(data, femto_bound)]
    print('After filter {!s:<13} {:.2f}% left'.format('femtoflux', 100*len(data)/startlen))
    gc.collect()

    # Alternatively:
    #data = data.loc[filter_negative(data) & filter_ck(data, ck_bound) & filter_totsep(data, septot_factor)]

    return data
    #for col in data.columns:
    #    splitted = re.compile('(?=.*)(.)(|ITG|ETG|TEM)_(GB|SI|cm)').split(col)
    #    if splitted[0] in particle_vars + heat_vars:
    #        if splitted[2] != '':
    #            data.loc[]

def separate_to_store(input, data, const, storename):
    store = pd.HDFStore(storename)
    store['input'] = input.loc[data.index]
    for col in data:
        splitted = re.compile('(?=.*)(.)(|ITG|ETG|TEM)_(GB|SI|cm)').split(col)
        if splitted[0] in heat_vars + particle_vars + momentum_vars + ['gam_leq_GB', 'gam_less_GB']:
            store.put(col, data[col].dropna(), format=store_format)
    store.put('constants', const)
    store.close()

def create_divsum(store):
    for group in store:
        group = group[1:]
        splitted = re.compile('(?=.*)(.)(|ITG|ETG|TEM)(_GB|SI|cm)').split(group)
        if splitted[0] in heat_vars and splitted[1] == 'i' and len(splitted) == 5:
            group2 = splitted[0] + 'e' + ''.join(splitted[2:])
            for name, set in [('_'.join([group, 'plus', group2]),
                              store[group] + store[group2]),
                              ('_'.join([group, 'div', group2]),
                               store[group] / store[group2])]:
                set.name = name
                store.put(set.name, set, format=store_format)
        if splitted[0] == 'pf' and splitted[1] == 'e' and len(splitted) == 5:
            group2 = 'efi' + ''.join(splitted[2:])
            group3 = 'efe' + ''.join(splitted[2:])
            for name, set in [
                ('_'.join([group, 'plus', group2, 'plus', group3]),
                 store[group] + store[group2] + store[group3]),
                ('_'.join([group, 'div', group2]),
                 store[group] / store[group2]),
                ('_'.join([group, 'div', group3]),
                 store[group] / store[group3])
            ]:
                print(name)
                set.name = name
                store.put(set.name, set, format=store_format)

def split_subsets(input, data, const, frac=0.1):
    rand_index = pd.Int64Index(np.random.permutation(input.index))
    idx = {}
    sep_index = int(frac * len(rand_index))
    idx['test'] = rand_index[:sep_index]
    idx['training'] = rand_index[sep_index:]
    embed()

    consts = {9: const.copy(),
              7: const.copy(),
              4: const.copy()}
    idx[7] = input.index[(
        np.isclose(input['Zeffx'], 1,     atol=1e-5, rtol=1e-3) &
        np.isclose(input['Nustar'], 1e-3, atol=1e-5, rtol=1e-3)
    )]

    inputs = {9: input}
    idx[9] = input.index
    inputs[7] = input.loc[idx[7]]
    for name in ['Zeffx', 'Nustar']:
        consts[7][name] = inputs[7].head(1)[name]
    inputs[7].drop(['Zeffx', 'Nustar'], axis='columns', inplace=True)

    idx[4] = inputs[7].index[(
        np.isclose(inputs[7]['Ate'], 6.5,     atol=1e-5, rtol=1e-3) &
        np.isclose(inputs[7]['An'], 2, atol=1e-5, rtol=1e-3) &
        np.isclose(inputs[7]['x'], 0.45, atol=1e-5, rtol=1e-3)
    )]
    inputs[4] = inputs[7].loc[idx[4]]
    for name in ['Ate', 'An', 'x']:
        consts[4][name] = inputs[4].head(1)[name]
    inputs[4].drop(['Ate', 'An', 'x'], axis='columns', inplace=True)

    for dim, set in product([9, 7, 4], ['test', 'training']):
        print(dim, set)
        store = pd.HDFStore(set + '_' + 'gen2_' + str(dim) + 'D_nions0_flat.h5')
        store['/megarun1/flattened'] = data.loc[idx[dim] & idx[set]]
        store['/megarun1/input'] = inputs[dim].loc[idx[set]]
        store['/megarun1/constants'] = consts[dim]
        store.close()

if __name__ == '__main__':
    dim = 9

    store_name = ''.join(['gen2_', str(dim), 'D_nions0_flat'])
    store = pd.HDFStore('../' + store_name + '.h5', 'r')

    input = store['/megarun1/input']
    data = store['/megarun1/flattened']

    startlen = len(data)
    data = sanity_filter(data, 50, 1.5, 1.5, 1e-4, startlen=startlen)
    data = regime_filter(data, 0, 100)
    gc.collect()
    input = input.loc[data.index]
    print('After filter {!s:<13} {:.2f}% left'.format('regime', 100*len(data)/startlen))
    filter_num = 7
    sane_store = pd.HDFStore('../sane_' + store_name + '_filter' + str(filter_num) + '.h5')
    sane_store['/megarun1/input'] = input
    sane_store['/megarun1/flattened'] = data
    const = sane_store['/megarun1/constants'] = store['/megarun1/constants']
    #input = sane_store['/megarun1/input']
    #data = sane_store['/megarun1/flattened']
    #const = sane_store['/megarun1/constants']
    sane_store.close()
    split_subsets(input, data, const, frac=0.1)
    del data, input, const
    gc.collect()


    for dim, set in product([4, 7, 9], ['test', 'training']):
        print(dim, set)
        basename = set + '_' + 'gen2_' + str(dim) + 'D_nions0_flat.h5'
        store = pd.HDFStore(basename)
        data = store['/megarun1/flattened']
        input = store['/megarun1/input']
        const = store['/megarun1/constants']

        gam = data['gam_leq_GB']
        gam = gam[gam != 0]
        data = stability_filter(data)
        data.put('gam_leq_GB', gam, format=store_format)
        separate_to_store(input, data, const, 'unstable_' + basename)
    #separate_to_store(input, data, '../filtered_' + store_name + '_filter6')
