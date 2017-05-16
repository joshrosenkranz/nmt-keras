import logging
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(message)s', datefmt='%d/%m/%Y %H:%M:%S')

from keras import backend as K
from keras.layers import Input, Lambda
from keras.models import Model
from keras.optimizers import PAS, PPAS
from keras.objectives import log_diff
from keras.utils.visualize_util import plot
def build_online_models(models, params):

    trainer_models = []
    if params['USE_CUSTOM_LOSS']:
        logging.info('Using custom loss.')
        # Add additional input layer to models in order to train with custom loss function
        for nmt_model in models:

            hyp = Input(name="hyp", batch_shape=tuple([None, None, None]))
            yref = Input(name="yref", batch_shape=tuple([None, None, None]))

            state_y = Input(name="state_y", batch_shape=tuple([None, None]))
            state_h = Input(name="state_h", batch_shape=tuple([None, None]))

            # Alternative 1: (P)PAS taking into account both h and y.
            if params['USE_H_Y']:
                x = Input(name="x", batch_shape=tuple([None, None]))

                preds_y = nmt_model.model([x, state_y])
                preds_h = nmt_model.model([x, state_h])

                loss_out = Lambda(log_diff,
                                  output_shape=(1,),
                                  name='custom_loss',
                                  supports_masking=False)([preds_y, yref, preds_h, hyp])

                trainer_model = Model(input=[x, state_y, state_h, yref, hyp],
                                      output=loss_out)
                plot(trainer_model, to_file='model_y_h.png')
                trainer_models.append(trainer_model)
            else:
                # Alternative 2: Apply optimization on y, based on h and y loss.
                preds_h = Input(name="state_h", batch_shape=tuple([None, None, None]))
                #predictor_model = Model(input=nmt_model.model.inputs,
                #                        output=nmt_model.model.outputs[0])

                loss_out = Lambda(log_diff,
                                  output_shape=(1,),
                                  name='custom_loss',
                                  supports_masking=False)([nmt_model.model.outputs[0], yref,
                                                           preds_h, hyp])

                trainer_model = Model(input=nmt_model.model.inputs + [preds_h] + [yref, hyp],
                                      output=loss_out)
                plot(trainer_model, to_file='model_y.png')
                trainer_models.append([trainer_model, nmt_model.model])
            exit(1)
            # Set custom optimizer
            weights = trainer_model.trainable_weights
            if not weights:
                logging.warning("You don't have any trainable weight!!")
            weights.sort(key=lambda x: x.name if x.name else x.auto_name)
            weights_shapes = [K.get_variable_shape(w) for w in weights]
            subgradientOpt = eval(params['OPTIMIZER'])(weights_shapes,
                                                       lr=params['LR'],
                                                       c=params['C'])
            trainer_model.compile(loss={'custom_loss': lambda y_true, y_pred: y_pred},
                                  optimizer=subgradientOpt)
            for nmt_model in models:
                nmt_model.setParams(params)
        return trainer_models
    else:
        for nmt_model in models:
            nmt_model.setParams(params)
            nmt_model.setOptimizer()
        return models