import keras
from keras.callbacks import Callback
import tensorflow as tf
import numpy as np
from keras import backend as K


class RewiringCallback(Callback):

    def __init__(self, connectivity_proportion, soft_limit=False, fixed_conn=False):
        super(RewiringCallback, self).__init__()
        self.connectivity_proportion = connectivity_proportion
        self.soft_limit = soft_limit
        self.fixed_conn = fixed_conn
        self._data = {
            'no_connections': {},
            'proportion_connections': {},
        }
        self._batch_rewires = {}

    @staticmethod
    def get_kernels_and_masks(model):
        kernels = []
        masks = []
        layers = []
        for layer in model.layers:
            if hasattr(layer, "kernel"):
                kernels.append(K.get_value(layer.kernel))
                masks.append(K.get_value(layer.mask))
                layers.append(layer)
        return np.asarray(kernels), np.asarray(masks), layers

    def on_batch_begin(self, batch, logs=None):
        # save the weights before updating to compare sign later
        self.pre_kernels, self.pre_masks, _ = \
            RewiringCallback.get_kernels_and_masks(self.model)

    def on_batch_end(self, batch, logs=None):
        logs = logs or {}
        # retrieve the new weights (after a batch)
        self.post_kernels, self.post_masks, self.layers = \
            RewiringCallback.get_kernels_and_masks(self.model)

        for k, m, l, i in zip(self.post_kernels, self.post_masks, self.layers,
                           np.arange(len(self.layers))):
            # If you invert the mask, are all those entries in kernel == 0?
            assert np.all(k[~m.astype(bool)] == 0)
            # TODO add aditional checks here,
            # check that pre and post masks are identical

            # check that the connectivity is at the correct amount
            assert (np.sum(m) / float(m.size) == self.connectivity_proportion[i])

        for pre_m, post_m in zip(self.pre_masks, self.post_masks):
            assert np.all(pre_m == post_m)

        if self.fixed_conn:
            # ASSESSING THE PERFORMANCE OF THE NETWORK WHEN THE CONNECTIVITY
            # IS SPARSE, BUT REWIRING IS DISABLED
            return

        # Let's rewire!
        for pre_m, post_m, pre_k, post_k, l in zip(
                self.pre_masks, self.post_masks,
                self.pre_kernels, self.post_kernels,
                self.layers):
            pre_sign = np.sign(pre_k)
            post_sign = np.sign(post_k)
            # compute which entries have change sign
            # can't use XOR here
            # https://stackoverflow.com/questions/3843017/efficiently-detect-sign-changes-in-python/21171725
            # retrieve indices of synapses which require rewiring
            need_rewiring = np.where(pre_sign - post_sign)

            # set old and new weights (kernel values) to 0
            # K.set_value()
            # new_k = post_k
            # new_k[need_rewiring] = 0
            # K.set_value(l.kernel, new_k)

            # update the mask by selecting other synapses to be active
            number_needing_rewiring = need_rewiring[0].size
            post_m[need_rewiring] = 0
            rewiring_candidates = np.where(post_m == 0)
            chosen_partners = np.random.choice(
                np.arange(rewiring_candidates[0].size),
                number_needing_rewiring,
                replace=False)

            new_m = post_m
            new_m[rewiring_candidates[0][chosen_partners], rewiring_candidates[1][chosen_partners]] = 1
            # enable the new connections
            K.set_value(l.mask, new_m)
            ...

        # old_sign = []
        # for row, ws in enumerate(self.weights_before_learning):
        #     old_sign.append(np.sign(ws))
        # new_sign = []
        # for row, ws in enumerate(new_weights):
        #     new_sign.append(np.sign(ws))
        # old_sign = np.asarray(old_sign)
        # new_sign = np.asarray(new_sign)
        # sign_changed = []
        # for old, new in zip(old_sign, new_sign):
        #     sign_changed.append(np.logical_xor(old, new))

        # for layer in self.model.layers:
        #     new_k = K.get_value(layer.kernel) * K.get_value(layer.mask)
        #     K.set_value(layer.kernel, new_k)

        # Operations can be done using
        # K.get_value(x):
        # and K.set_value(x, value)

        # reporting stuff

    def on_epoch_end(self, epoch, logs=None):
        print("\nEpoch {:3} results:".format(epoch))
        for k, m, l in zip(self.post_kernels, self.post_masks, self.layers):
            self._data['no_connections'][epoch] = np.sum(m)
            self._data['proportion_connections'][epoch] = np.sum(m) / float(m.size)
            print("Layer {:10} has {:8} connections, corresponding to "
                  "{:>5.1%} of "
                  "the total connectivity".format(
                l.name,
                self._data['no_connections'][epoch],
                self._data['proportion_connections'][epoch]))

    def stats(self):
        return {
            "epoch_data": self._data,
            "batch_data": self._batch_rewires
        }
