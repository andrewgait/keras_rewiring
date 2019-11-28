from keras_rewiring.experiments.common import *
# network generation imports
from keras_rewiring.experiments.mnist.lenet_300_100_model_setup import \
    generate_lenet_300_100_model, \
    generate_sparse_lenet_300_100_model

start_time = plt.datetime.datetime.now()
# Setting number of CPUs to use
set_nslots()

# Setting up directory structure
setup_directory_structure()


is_output_categorical = True
dataset_info = load_and_preprocess_dataset(
    'mnist', categorical_output=is_output_categorical)
x_train, y_train = dataset_info['train']
x_test, y_test = dataset_info['test']
img_rows, img_cols = dataset_info['img_dims']
input_shape = dataset_info['input_shape']
num_classes = dataset_info['num_classes']

# reshape input to flatten data
x_train = x_train.reshape(x_train.shape[0], 1, np.prod(x_train.shape[1:]))
x_test = x_test.reshape(x_test.shape[0], 1, np.prod(x_test.shape[1:]))

print(x_train.shape)
epochs = args.epochs or 10
batch = 10
learning_rate = 0.5
decay_rate = 0.8  # changed from 0.8

connectivity_proportion = [.01, .03, .3]

# Retrieve optimizer and its name (for files and reports)
optimizer, optimizer_name = extract_optimizer_from_args(learning_rate)


loss = keras.losses.categorical_crossentropy

builtin_sparsity = [.01, .03, .3]
final_conns = np.asarray(builtin_sparsity)

conn_decay_values = None
if args.conn_decay:
    conn_decay_values = (np.log(1. / final_conns)/epochs).tolist()
    builtin_sparsity = np.ones(len(conn_decay_values)).tolist()

if not args.sparse_layers:
    model = generate_lenet_300_100_model(
        activation=args.activation,
        categorical_output=is_output_categorical)
elif args.sparse_layers and not args.soft_rewiring:
    if args.conn_decay:
        print("Connectivity decay rewiring enabled", conn_decay_values)
        model = generate_sparse_lenet_300_100_model(
            activation=args.activation,
            categorical_output=is_output_categorical,
            builtin_sparsity=builtin_sparsity,
            conn_decay=conn_decay_values)
    else:
        model = generate_sparse_lenet_300_100_model(
            activation=args.activation,
            categorical_output=is_output_categorical,
            builtin_sparsity=builtin_sparsity)
else:
    print("Soft rewiring enabled", args.soft_rewiring)
    model = generate_sparse_lenet_300_100_model(
        activation=args.activation,
        categorical_output=is_output_categorical)
model.summary()

# disable rewiring with sparse layers to see the performance of the layer
# when 90% of connections are disabled and static
deep_r = RewiringCallback(fixed_conn=args.disable_rewiring,
                          soft_limit=args.soft_rewiring,
                          noise_coeff=10 ** -5,
                          asserts_on=args.asserts_on)
model.compile(
    optimizer=optimizer,
    loss=loss,
    metrics=['accuracy', keras.metrics.top_k_categorical_accuracy])

suffix = ""
if args.suffix:
    suffix = "_" + args.suffix

if args.model[0] == ":":
    model_name = args.model[1:]
else:
    model_name = args.model

output_filename = ""
if args.result_filename:
    output_filename = args.result_filename
else:
    output_filename = "results_for_" + model_name
activation_name = "relu"
loss_name = "crossent"
if args.sparse_layers:
    if args.soft_rewiring:
        sparse_name = "sparse_soft"
    else:
        if args.conn_decay:
            sparse_name = "sparse_decay"
        else:
            sparse_name = "sparse_hard"
else:
    sparse_name = "dense"

output_filename += "_" + activation_name
output_filename += "_" + loss_name
output_filename += "_" + sparse_name
output_filename += "_" + optimizer_name + suffix
output_filename += ".csv"

csv_path = os.path.join(args.result_dir, output_filename)
csv_logger = keras.callbacks.CSVLogger(
    csv_path,
    separator=',',
    append=False)

callback_list = []
if args.sparse_layers:
    callback_list.append(deep_r)

if args.tensorboard:
    tb_log_filename = "./sparse_logs" if args.sparse_layers else "./dense_logs"

    tb = keras.callbacks.TensorBoard(
        log_dir=tb_log_filename,
        histogram_freq=0,  # turning this on needs validation_data in model.fit
        batch_size=batch, write_graph=True,
        write_grads=True, write_images=True,
        embeddings_freq=0, embeddings_layer_names=None,
        embeddings_metadata=None, embeddings_data=None,
        update_freq='epoch')
    callback_list.append(tb)

callback_list.append(csv_logger)
model.fit(x_train, y_train,
# model.fit(x_train[:100], y_train[:100],
          batch_size=batch,
          epochs=epochs,
          verbose=1,
          callbacks=callback_list,
          validation_data=(x_test, y_test),
          # validation_split=.2
          )

score = model.evaluate(x_test, y_test, verbose=1, batch_size=batch)
print('Test Loss:', score[0])
print('Test Accuracy:', score[1])

end_time = plt.datetime.datetime.now()
total_time = end_time - start_time
print("Total time elapsed -- " + str(total_time))

model_path = os.path.join(
    args.model_dir,
    "trained_model_of_" + model_name + "_" + activation_name +
    "_" + loss_name +
    "_" + optimizer_name + suffix + ".h5")

model.save(model_path)

print("Results (csv) saved at", csv_path)
print("Model saved at", model_path)