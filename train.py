import numpy as np

import torch
import torch.nn.functional as F
from tqdm import tqdm
try:
    from visdom import Visdom
except Exception:
    pass

from util import variable, idx2text, save_weights


def check_random_example(dataset, model, idx2w):
    """
    Check a random test sentence and its autoencoder reconstruction
    Args:
        dataset: AutoencoderDataset
        model: Autoencoder model
        idx2w (dict): A reversed dictionary matching ids to tokens

    Returns (tuple): input training sentence and its reconstruction

    """
    random_idx = np.random.randint(len(dataset))
    input = dataset[random_idx]
    input = variable(input)
    output = model(input.unsqueeze(0)).squeeze()

    _, words = torch.max(F.softmax(output, dim=-1), dim=1)
    input_text = idx2text(list(input.cpu().numpy()), idx2w)
    predicted_text = idx2text(list(words.cpu().numpy()), idx2w)
    return input_text, predicted_text


def train(model, filename, criterion, optimizer, dataloaders, n_epochs, idx2w, pad_idx, max_grad_norm=5, port=None):
    """
    The model training function. Saves a model to a specified location if the loss on the dev set reaches a new minimum
    Args:
        model:
        filename (str):  A path for saving a trained model
        criterion: Used loss function
        optimizer: torch optimizer
        dataloaders (dict): a dictionary of a train and test DataLoader objects
        n_epochs: Number of epochs
        idx2w (dict): A reversed dictionary matching ids to tokens
        max_grad_norm (optional): Maximum magnitude of gradients (for clipping)
        port: Used for connecting to Visdom server and visualizing the learning curve

    """

    parameters = [parameter for parameter in list(model.parameters()) if parameter.requires_grad]

    # Prepare for visualization if Visdom server is running
    if port:
        viz = Visdom(port=port)

    best = None

    for epoch in range(1, n_epochs + 1):
        for phase in ['train', 'dev']:
            if phase == 'train':
                model.train(True)
                losses_train = 0
                batch_train = 0
            else:
                model.train(False)
                losses_dev = 0
                batch_dev = 0
            for i_batch, sample_batched in enumerate(tqdm(dataloaders[phase])):
                inputs = sample_batched
                inputs = variable(inputs)

                outputs = model(inputs)

                targets = inputs.view(-1)
                outputs = outputs.view(targets.shape[0], -1)

                loss = criterion(outputs, targets)

                if phase == 'train':
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(parameters, max_grad_norm)
                    optimizer.step()
                    losses_train += loss.item()
                    batch_train += 1
                else:
                    losses_dev += loss.item()
                    batch_dev += 1

                if i_batch % 500 == 0:
                    print('_________________________________________')
                    print('Epoch #{}'.format(epoch))

                    if phase == 'dev':
                        loss_dev = losses_dev/(i_batch+1)
                        print('DEV  \t loss: {:.4f}'.format(loss_dev))
                        if best is None or loss_dev < best:
                            best = loss.item()
                            save_weights(model, filename)

                    elif phase == 'train':
                        loss_train = losses_train/(i_batch+1)
                        print('TRAIN \t loss: {:.4f}'.format(loss_train))

                    # Check outputs on a random example
                    input_text, predicted_text = check_random_example(dataloaders[phase].dataset, model, idx2w)
                    print("{: <20} {}".format("Input:", input_text))
                    print("{: <20} {}".format("Reconstructed:", predicted_text))

        epoch_loss_train = losses_train/batch_train
        epoch_loss_dev = losses_dev/batch_dev
        if port:
            if epoch == 1:
                viz.line(X=np.array([epoch]), Y=np.expand_dims(np.array([epoch_loss_train, epoch_loss_dev]), axis=0), win='AutoencoderLoss',
                         opts={'title': 'Loss', 'legend': ['Train', 'Dev']}, )
            else:
                viz.line(X=np.array([epoch]), Y=np.expand_dims(np.array([epoch_loss_train, epoch_loss_dev]), axis=0),
                     win='AutoencoderLoss', update="append", opts={'title': 'Loss', 'legend': ['Train', 'Dev']})


