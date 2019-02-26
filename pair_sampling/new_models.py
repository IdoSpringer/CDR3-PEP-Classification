import torch
import torch.autograd as autograd
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

# todo dropout (in MLP? more layers in LSTM?)

class SiameseLSTMClassifier(nn.Module):
    def __init__(self, embedding_dim, lstm_dim, device):
        super(SiameseLSTMClassifier, self).__init__()
        # GPU
        self.device = device
        # Dimensions
        self.embedding_dim = embedding_dim
        self.lstm_dim = lstm_dim
        # Embedding matrix - 20 amino acids + padding
        self.embedding = nn.Embedding(20 + 1, embedding_dim, padding_idx=0)
        # RNN - LSTM
        self.lstm = nn.LSTM(embedding_dim, lstm_dim, num_layers=1, batch_first=True)
        # MLP
        self.hidden_layer = nn.Linear(lstm_dim * 2, lstm_dim)
        self.relu = torch.nn.LeakyReLU()
        self.output_layer = nn.Linear(lstm_dim, 1)
        # self.hidden = self.init_hidden()

    def init_hidden(self, batch_size):
        return (autograd.Variable(torch.zeros(1, batch_size, self.lstm_dim)).to(self.device),
                autograd.Variable(torch.zeros(1, batch_size, self.lstm_dim)).to(self.device))

    def lstm_pass(self, padded_embeds, lengths):
        # Before using PyTorch pack_padded_sequence we need to order the sequences batch by descending sequence length
        lengths, perm_idx = lengths.sort(0, descending=True)
        padded_embeds = padded_embeds[perm_idx]
        # Pack the batch and ignore the padding
        padded_embeds = torch.nn.utils.rnn.pack_padded_sequence(padded_embeds, lengths, batch_first=True)
        # Initialize the hidden state
        batch_size = len(lengths)
        hidden = self.init_hidden(batch_size)
        # Feed into the RNN
        lstm_out, hidden = self.lstm(padded_embeds, hidden)
        # Unpack the batch after the RNN
        lstm_out, lengths = torch.nn.utils.rnn.pad_packed_sequence(lstm_out, batch_first=True)
        # Remember that our outputs are sorted. We want the original ordering
        _, unperm_idx = perm_idx.sort(0)
        lstm_out = lstm_out[unperm_idx]
        lengths = lengths[unperm_idx]
        return lstm_out

    def forward(self, tcrs, tcr_lens, peps, pep_lens):
        # TCR Encoder:
        # Embedding
        tcr_embeds = self.embedding(tcrs)
        # LSTM Acceptor
        tcr_lstm_out = self.lstm_pass(tcr_embeds, tcr_lens)
        tcr_last_cell = torch.cat([tcr_lstm_out[i, j.data - 1] for i, j in enumerate(tcr_lens)]).view(len(tcr_lens), self.lstm_dim)

        # PEPTIDE Encoder:
        # Embedding
        pep_embeds = self.embedding(peps)
        # LSTM Acceptor
        pep_lstm_out = self.lstm_pass(pep_embeds, pep_lens)
        pep_last_cell = torch.cat([pep_lstm_out[i, j.data - 1] for i, j in enumerate(pep_lens)]).view(len(pep_lens), self.lstm_dim)

        # MLP Classifier
        tcr_pep_concat = torch.cat([tcr_last_cell, pep_last_cell], 1)
        hidden_output = self.relu(self.hidden_layer(tcr_pep_concat))
        mlp_output = self.output_layer(hidden_output)
        output = F.sigmoid(mlp_output)
        return output


class DoubleLSTMClassifier(nn.Module):
    def __init__(self, embedding_dim, lstm_dim, dropout, device):
        super(DoubleLSTMClassifier, self).__init__()
        # GPU
        self.device = device
        # Dimensions
        self.embedding_dim = embedding_dim
        self.lstm_dim = lstm_dim
        self.dropout = dropout
        # Embedding matrices - 20 amino acids + padding
        self.tcr_embedding = nn.Embedding(20 + 1, embedding_dim, padding_idx=0)
        self.pep_embedding = nn.Embedding(20 + 1, embedding_dim, padding_idx=0)
        # RNN - LSTM
        self.tcr_lstm = nn.LSTM(embedding_dim, lstm_dim, num_layers=2, batch_first=True, dropout=dropout)
        self.pep_lstm = nn.LSTM(embedding_dim, lstm_dim, num_layers=2, batch_first=True, dropout=dropout)
        # MLP
        self.hidden_layer = nn.Linear(lstm_dim * 2, lstm_dim)
        self.relu = torch.nn.LeakyReLU()
        self.output_layer = nn.Linear(lstm_dim, 1)
        self.dropout = nn.Dropout(p=dropout)

    def init_hidden(self, batch_size):
        return (autograd.Variable(torch.zeros(2, batch_size, self.lstm_dim)).to(self.device),
                autograd.Variable(torch.zeros(2, batch_size, self.lstm_dim)).to(self.device))

    def lstm_pass(self, lstm, padded_embeds, lengths):
        # Before using PyTorch pack_padded_sequence we need to order the sequences batch by descending sequence length
        lengths, perm_idx = lengths.sort(0, descending=True)
        padded_embeds = padded_embeds[perm_idx]
        # Pack the batch and ignore the padding
        padded_embeds = torch.nn.utils.rnn.pack_padded_sequence(padded_embeds, lengths, batch_first=True)
        # Initialize the hidden state
        batch_size = len(lengths)
        hidden = self.init_hidden(batch_size)
        # Feed into the RNN
        lstm_out, hidden = lstm(padded_embeds, hidden)
        # Unpack the batch after the RNN
        lstm_out, lengths = torch.nn.utils.rnn.pad_packed_sequence(lstm_out, batch_first=True)
        # Remember that our outputs are sorted. We want the original ordering
        _, unperm_idx = perm_idx.sort(0)
        lstm_out = lstm_out[unperm_idx]
        lengths = lengths[unperm_idx]
        return lstm_out

    def forward(self, tcrs, tcr_lens, peps, pep_lens):
        # TCR Encoder:
        # Embedding
        tcr_embeds = self.tcr_embedding(tcrs)
        # LSTM Acceptor
        tcr_lstm_out = self.lstm_pass(self.tcr_lstm, tcr_embeds, tcr_lens)
        tcr_last_cell = torch.cat([tcr_lstm_out[i, j.data - 1] for i, j in enumerate(tcr_lens)]).view(len(tcr_lens), self.lstm_dim)

        # PEPTIDE Encoder:
        # Embedding
        pep_embeds = self.pep_embedding(peps)
        # LSTM Acceptor
        pep_lstm_out = self.lstm_pass(self.pep_lstm, pep_embeds, pep_lens)
        pep_last_cell = torch.cat([pep_lstm_out[i, j.data - 1] for i, j in enumerate(pep_lens)]).view(len(pep_lens), self.lstm_dim)

        # MLP Classifier
        tcr_pep_concat = torch.cat([tcr_last_cell, pep_last_cell], 1)
        # todo dropout
        hidden_output = self.dropout(self.relu(self.hidden_layer(tcr_pep_concat)))
        mlp_output = self.output_layer(hidden_output)
        output = F.sigmoid(mlp_output)
        return output
