import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import sys
from random import shuffle
import time
import numpy as np
import torch.autograd as autograd
from pair_sampling.new_models import SiameseLSTMClassifier, DoubleLSTMClassifier
import pair_sampling.load_data as d
from sklearn.metrics import roc_auc_score, roc_curve
import csv


def get_lists_from_pairs(pairs, mis):
    tcrs = []
    peps = []
    signs = []
    for pair in pairs:
        tcr, pep, label, weight = pair
        tcrs.append(tcr[:mis] + tcr[(mis + 1):])
        peps.append(pep)
        if label == 'p':
            signs.append(1.0)
        elif label == 'n':
            signs.append(0.0)
    return tcrs, peps, signs


def convert_data(tcrs, peps, amino_to_ix):
    for i in range(len(tcrs)):
        if any(letter.islower() for letter in tcrs[i]):
            print(tcrs[i])
        tcrs[i] = [amino_to_ix[amino] for amino in tcrs[i]]
    for i in range(len(peps)):
        peps[i] = [amino_to_ix[amino] for amino in peps[i]]


def get_batches(tcrs, peps, signs, batch_size):
    """
    Get batches from the data
    """
    # Initialization
    batches = []
    index = 0
    # Go over all data
    while index < len(tcrs):
        # Get batch sequences and math tags
        batch_tcrs = tcrs[index:index + batch_size]
        batch_peps = peps[index:index + batch_size]
        batch_signs = signs[index:index + batch_size]
        # Update index
        index += batch_size
        # Pad the batch sequences
        padded_tcrs, tcr_lens = pad_batch(batch_tcrs)
        padded_peps, pep_lens = pad_batch(batch_peps)
        # Add batch to list
        batches.append((padded_tcrs, tcr_lens, padded_peps, pep_lens, batch_signs))
    # Return list of all batches
    return batches


def pad_batch(seqs):
    """
    Pad a batch of sequences (part of the way to use RNN batching in PyTorch)
    """
    # Tensor of sequences lengths
    lengths = torch.LongTensor([len(seq) for seq in seqs])
    # The padding index is 0
    # Batch dimensions is number of sequences * maximum sequence length
    longest_seq = max(lengths)
    batch_size = len(seqs)
    # Pad the sequences. Start with zeros and then fill the true sequence
    padded_seqs = autograd.Variable(torch.zeros((batch_size, longest_seq))).long()
    for i, seq_len in enumerate(lengths):
        seq = seqs[i]
        padded_seqs[i, 0:seq_len] = torch.LongTensor(seq[:seq_len])
    # Return padded batch and the true lengths
    return padded_seqs, lengths


def train_epoch(batches, model, loss_function, optimizer, device):
    model.train()
    shuffle(batches)
    total_loss = 0
    for batch in batches:
        padded_tcrs, tcr_lens, padded_peps, pep_lens, batch_signs = batch
        # Move to GPU
        padded_tcrs = padded_tcrs.to(device)
        tcr_lens = tcr_lens.to(device)
        padded_peps = padded_peps.to(device)
        pep_lens = pep_lens.to(device)
        batch_signs = torch.tensor(batch_signs).to(device)
        model.zero_grad()
        probs = model(padded_tcrs, tcr_lens, padded_peps, pep_lens)
        # print(probs, batch_signs)
        # Compute loss
        loss = loss_function(probs, batch_signs)
        # with open(sys.argv[1], 'a+') as loss_file:
        #    loss_file.write(str(loss.item()) + '\n')
        # Update model weights
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        # print('current loss:', loss.item())
        # print(probs, batch_signs)
    # Return average loss
    return total_loss / len(batches)


def train_model(batches, test_batches, device, args, params):
    """
    Train and evaluate the model
    """
    losses = []
    # We use Cross-Entropy loss
    loss_function = nn.BCELoss()
    # Set model with relevant parameters
    if args['siamese'] is True:
        model = SiameseLSTMClassifier(params['emb_dim'], params['lstm_dim'], device)
    else:
        model = DoubleLSTMClassifier(params['emb_dim'], params['lstm_dim'], params['dropout'], device)
    # Move to GPU
    model.to(device)
    # We use Adam optimizer
    optimizer = optim.Adam(model.parameters(), lr=params['lr'], weight_decay=params['wd'])
    # Train several epochs
    best_auc = 0
    best_roc = None
    for epoch in range(params['epochs']):
        print('epoch:', epoch + 1)
        epoch_time = time.time()
        # Train model and get loss
        loss = train_epoch(batches, model, loss_function, optimizer, device)
        losses.append(loss)
        # Compute auc
        train_auc = evaluate(model, batches, device)[0]
        print('train auc:', train_auc)
        with open(args['train_auc_file'], 'a+') as file:
            file.write(str(train_auc) + '\n')
        if params['option'] == 2:
            '''
            test_w, test_c = test_batches
            test_auc_w = evaluate(model, test_w, device)
            print('test auc w:', test_auc_w)
            with open(args['test_auc_file_w'], 'a+') as file:
                file.write(str(test_auc_w) + '\n')
            test_auc_c = evaluate(model, test_c, device)
            print('test auc c:', test_auc_c)
            with open(args['test_auc_file_c'], 'a+') as file:
                file.write(str(test_auc_c) + '\n')
            '''
        else:
            test_auc, roc = evaluate(model, test_batches, device)
            if test_auc > best_auc:
                best_auc = test_auc
                best_roc = roc
            print('test auc:', test_auc)
            with open(args['test_auc_file'], 'a+') as file:
                file.write(str(test_auc) + '\n')
        print('one epoch time:', time.time() - epoch_time)
    return model, best_auc, best_roc


def evaluate(model, batches, device):
    model.eval()
    true = []
    scores = []
    shuffle(batches)
    for batch in batches:
        padded_tcrs, tcr_lens, padded_peps, pep_lens, batch_signs = batch
        # Move to GPU
        padded_tcrs = padded_tcrs.to(device)
        tcr_lens = tcr_lens.to(device)
        padded_peps = padded_peps.to(device)
        pep_lens = pep_lens.to(device)
        probs = model(padded_tcrs, tcr_lens, padded_peps, pep_lens)
        # print(np.array(batch_signs).astype(int))
        # print(probs.cpu().data.numpy())
        true.extend(np.array(batch_signs).astype(int))
        scores.extend(probs.cpu().data.numpy())
    # Return auc score
    auc = roc_auc_score(true, scores)
    fpr, tpr, thresholds = roc_curve(true, scores)
    return auc, (fpr, tpr, thresholds)


def main(argv):
    # Word to index dictionary
    amino_acids = [letter for letter in 'ARNDCEQGHILKMFPSTWYV']
    amino_to_ix = {amino: index for index, amino in enumerate(['PAD'] + amino_acids)}

    # Set all parameters and program arguments
    device = argv[1]
    args = {}
    # args['roc_file'] = argv[5]
    args['siamese'] = False
    params = {}
    params['lr'] = 1e-3
    params['wd'] = 1e-5
    params['epochs'] = 200
    params['batch_size'] = 50
    params['lstm_dim'] = 30
    params['emb_dim'] = 10
    params['dropout'] = 0.1
    params['option'] = 0

    # Load data
    pairs_file = 'pair_sampling/pairs_data/weizmann_pairs.txt'
    if argv[-1] == 'cancer':
        pairs_file = 'pair_sampling/pairs_data/cancer_pairs.txt'
    if argv[-1] == 'shugay':
        pairs_file = 'pair_sampling/pairs_data/shugay_pairs.txt'
    if argv[-1] == 'ex_cancer':
        pairs_file = 'extended_cancer_pairs.txt'
    if argv[-1] == 'exs_cancer':
        pairs_file = 'safe_extended_cancer_pairs.txt'
    if argv[-1] == 'exnos_cancer':
        pairs_file = 'no_shugay_extended_cancer_pairs.txt'

    train, test = d.load_data(pairs_file)
    tcr_max_len = max([len(t[0]) for t in train + test])

    tcr_max_len = 28

    dr = 'mis_pos_auc'
    # iterations = 10

    # Train the model
    for iteration in range(9, 10):
        for i in range(tcr_max_len):
            params['mis_index'] = i

            # train
            train_tcrs, train_peps, train_signs = get_lists_from_pairs(train, i)
            convert_data(train_tcrs, train_peps, amino_to_ix)
            train_batches = get_batches(train_tcrs, train_peps, train_signs, params['batch_size'])

            # test
            test_tcrs, test_peps, test_signs = get_lists_from_pairs(test, i)
            convert_data(test_tcrs, test_peps, amino_to_ix)
            test_batches = get_batches(test_tcrs, test_peps, test_signs, params['batch_size'])

            args['train_auc_file'] = dr + '/' + argv[2] + '_' + str(iteration) + '_' + str(i)
            args['test_auc_file'] = dr + '/' + argv[3] + '_' + str(iteration) + '_' + str(i)
            train_model(train_batches, test_batches, device, args, params)
    pass


if __name__ == '__main__':
    main(sys.argv)

