# TCR-peptide attachment prediction

(Report 22/2/19)

## Encoding TCRs

In previous attempts to build a model for predicting TCR and peptide
attachment, we used LSTM to encode both TCR and peptide. We tried a
different approach, using TCR autoencoder (based on Shirit's work).

### The Autoencoder

The autoencoder we use is based on zero-padding and linear layers, not
RNNs. Given a TCR, we first add a stop signal to the end of its amino-acid
sequence. Then, we convert the TCR to a sequence of one-hot vectors.
We make sure that all TCR sequences have the same max-length by
adding zero-padding vectors in the end of the sequences. It is necessary
because we use linear layers with fixed size. We concatenate the one-
hot vectors of the TCR sequence into a large vector, which is fed into the
encoder. The encoder (and the decoder) are composed from some linear
layers with dropout layers between them (and softmax to make one-hot
vectors). We use the encoder to encode the TCR into a fixed size vector,
and the decoder to decode that vector to a sequence of one-hot vectors
representing the TCR.

The autoencoder (implemented in PyTorch) can be found here: [autoencoder](https://github.com/IdoSpringer/TCR-PEP-Classification/blob/master/autoencoder_model.py)

### Autoencoder configurations

(based on Shirit's code in Keras)

**Dimensions:**  
Encoder: after we concatenate the one-hot vectors of the
TCR, we pass it through a linear layer to dense its size to 300, then 100,
and then the encoding dimension which is 30.

Decoder: we go the
reverse way, from the encoding dimension to 100 to 300 to the original
one-hot TCR dimensions. Then we use softmax.

**Activation:**  We use ELU activation between the linear layers.

**Dropout:**  We use dropout rate of 0.1 between the layers.

**Loss function:**  Mean squared error.

**Optimizer:** Adam, with learning rate = 1e-4, beta1 = 0.9, beta2 = 0.999,
epsilon = 1e-8, weight decay = 0.

**Batch size:**  50 (the batch size is fixed).

**Epochs:** the autoencoder is trained for 300 epochs