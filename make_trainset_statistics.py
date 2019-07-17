import torch
from torch.utils.data import DataLoader, ConcatDataset
from pase.dataset import PairWavDataset, DictCollater
from torchvision.transforms import Compose
from pase.transforms import *
import argparse
import pickle

def build_dataset_providers(opts):

    assert len(opts.data_root) > 0, (
        "Expected at least one data_root argument"
    )

    assert len(opts.data_root) == len(opts.data_cfg), (
        "Provide same number of data_root and data_cfg arguments"
    )

    trans = Compose([
        ToTensor(),
        MIChunkWav(opts.chunk_size),
        LPS(hop=opts.hop_size),
        MFCC(hop=opts.hop_size),
        Prosody(hop=opts.hop_size)
    ])

    dsets = []
    for idx in range(len(opts.data_root)):
        dset = PairWavDataset(opts.data_root[idx], opts.data_cfg[idx], 'train',
                         transform=trans)
        dsets.append(dset)

    if len(dsets) > 1:
        return ConcatDataset(dsets)
    else:
        return dsets[0]

def extract_stats(opts):
    dset = build_dataset_providers(opts)
    dloader = DataLoader(dset, batch_size = 100,
                         shuffle=True, collate_fn=DictCollater(),
                         num_workers=opts.num_workers)
    # Compute estimation of bpe. As we sample chunks randomly, we
    # should say that an epoch happened after seeing at least as many
    # chunks as total_train_wav_dur // chunk_size
    bpe = (dset.total_wav_dur // opts.chunk_size) // 500
    data = {}
    # run one epoch of training data to extract z-stats of minions
    for bidx, batch in enumerate(dloader, start=1):
        print('Bidx: {}/{}'.format(bidx, bpe))
        for k, v in batch.items():
            if k not in data:
                data[k] = []
            data[k].append(v)

        if bidx >= opts.max_batches:
            break

    stats = {}
    data = dict((k, torch.cat(v)) for k, v in data.items())
    for k, v in data.items():
        stats[k] = {'mean':torch.mean(torch.mean(v, dim=2), dim=0),
                    'std':torch.std(torch.std(v, dim=2), dim=0)}
    with open(opts.out_file, 'wb') as stats_f:
        pickle.dump(stats, stats_f)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_root', action='append', 
                        default='data/LibriSpeech/Librispeech_spkid_sel')
    parser.add_argument('--data_cfg', action='append', 
                        default='data/librispeech_data.cfg')
    parser.add_argument('--exclude_keys', type=str, nargs='+', 
                        default=['chunk', 'chunk_rand', 'chunk_ctxt'])
    parser.add_argument('--num_workers', type=int, default=1)
    parser.add_argument('--chunk_size', type=int, default=16000)
    parser.add_argument('--max_batches', type=int, default=20)
    parser.add_argument('--out_file', type=str, default='data/librispeech_stats.pkl')
    parser.add_argument('--hop_size', type=int, default=160)

    opts = parser.parse_args()
    extract_stats(opts)
