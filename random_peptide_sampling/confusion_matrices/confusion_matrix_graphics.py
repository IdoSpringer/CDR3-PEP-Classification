import itertools
import numpy as np
import matplotlib.pyplot as plt
import sys


from sklearn import svm, datasets
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix


def read_conf_from_file(filename):
    with open(filename, 'r') as file:
        array = []
        for line in file:
            line = line.replace('[', "")
            line = line.replace(']', "")
            line = line.replace('.', "")
            line = line.split()
            for i in range(len(line)):
                line[i] = int(line[i])
            array.append(line)
    return np.array(array)


def plot_confusion_matrix(cm, classes,
                          normalize=False,
                          title='Confusion matrix',
                          cmap=plt.cm.Blues):
    """
    This function prints and plots the confusion matrix.
    Normalization can be applied by setting `normalize=True`.
    """
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        print("Normalized confusion matrix")
    else:
        print('Confusion matrix, without normalization')

    print(cm)

    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    # tick_marks = np.arange(len(classes))
    # plt.xticks(tick_marks, classes, rotation=45)
    # plt.yticks(tick_marks, classes)

    fmt = '.2f' if normalize else 'd'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if cm[i, j] > thresh else "black")

    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()


# Compute confusion matrix
'''
confusion matrix: (regular, w, 8)
[[314.  64.  46.   7.   1.   4.  11.   6.]
 [107. 198.  26.   8.   0.   0.   3.   2.]
 [ 88.  21.  51.  33.   0.   1.  10.   9.]
 [ 58.  20.  20.  56.   0.   0.   9.   4.]
 [  8.   1.   3.   2.  96.  11.   3.   4.]
 [ 12.   8.   4.   0.  16.  34.   9.  27.]
 [ 15.  17.  14.   1.   0.   4.  24.   3.]
 [ 10.   2.   5.   2.  17.  15.   2.  48.]]
'''
cnf_matrix = read_conf_from_file(sys.argv[1])
class_names = ['LPRRSGAAGA', 'GILGFVFTL', 'GLCTLVAML', 'NLVPMVATV', 'SSYRRPVGI', 'SSLENFRAYV', 'RFYKTLRAEQASQ', 'ASNENMETM']
np.set_printoptions(precision=2)

# Plot non-normalized confusion matrix
# plt.figure()
# plot_confusion_matrix(cnf_matrix, classes=class_names,
# title='Confusion matrix, without normalization')

# Plot normalized confusion matrix
plt.figure()
plot_confusion_matrix(cnf_matrix, classes=class_names, normalize=True,
                      title='Normalized confusion matrix, loss * (all_tcr / tcr_per_pep)')

plt.show()