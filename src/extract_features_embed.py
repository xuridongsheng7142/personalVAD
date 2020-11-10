import numpy as np
import os
import io
from enum import Enum
import sys
import pickle
import shlex, subprocess
import soundfile as sf
import python_speech_features as psf
from glob import glob
from resemblyzer import VoiceEncoder, preprocess_wav

from extract_features import replace_zero_sequences

# Path to the dataset
DATA = 'data/concat/'
DEST = 'data/features/'
TEXT = 'data/concat/text'
LIBRI_SOURCE = 'data/LibriSpeech/dev-clean/'

# feature extraction mode based on the target architecture
class Mode(Enum):
    VAD = 0
    SC = 1
    ST = 2
    ET = 3
    SET = 4

MODE = Mode.ET

def get_speaker_embedding(utt_id, spk_idx, encoder, n_wavs=2):
    # first remove the augmentation prefix...
    if 'rev' in utt_id:
        utt_id = utt_id.partition('-')[2]

    # get the speaker id
    spk_id = utt_id.split('_')[spk_idx].split('-')

    # now, compute the speaker embedding from a few audio files in their librispeech folder..
    files = glob(LIBRI_SOURCE + spk_id[0] + '/' + spk_id[1] + '/*.flac')
    wavs = list()
    for i in range(n_wavs):
        random_file = np.random.randint(0, n_wavs)
        wavs.append(preprocess_wav(sf.read(files[random_file])[0]))

    return encoder.embed_speaker(wavs)

def features_from_flac(text):
    encoder = VoiceEncoder()
    with os.scandir(DATA) as folders:
        for folder in folders:
            print(f'Entering folder {folder.name}')
            os.mkdir(DEST + folder.name)

            for f in glob(folder.path + '/*.flac'):
                utt_id = f.rpartition('/')[2].split('.')[0]

                # first, extract the log mel-filterbank energies
                x, sr = sf.read(f)
                assert (sr == 16000), f'Invalid source audio sample rate {sr}'
                fbanks, energy = psf.base.fbank(x, nfilt=40, winfunc=np.hamming)
                logfbanks = np.log10(fbanks)

                # now load the transcription and the alignment timestamps
                gtruth, tstamps = text[utt_id]
                gt_len = len(gtruth)
                assert (gt_len == tstamps.size), f"gtruth and tstamps arrays have to be the same"

                # now generate n ground truth labels based on the gtruth and tstamps labels
                # where n is the number of feature frames we extracted
                n = logfbanks.shape[0]

                # NOTE: the timestamp doesn't really match the value of n. Keep an eye out..
                if tstamps[-1] < n*10:
                    tstamps[-1] = n * 10

                # classic vad
                if MODE == Mode.VAD:
                    labels = np.ones(n)
                    stamp_prev = 0
                    tstamps = tstamps // 10

                    for (stamp, label) in zip(tstamps, gtruth):
                        if label in ['', '$']: labels[stamp_prev:stamp] = 0
                        stamp_prev = stamp

                    with open(DEST + folder.name + '/' + utt_id + '.vad.fea', 'wb') as f:
                        pickle.dump((logfbanks, replace_zero_sequences(labels, 8)), f)

                elif MODE == Mode.SC:
                    pass #TODO
                elif MODE == Mode.ST:
                    pass #TODO

                # target embedding vad
                elif MODE == Mode.ET:

                    # now onto d-vector extraction...
                    #wav = preprocess_wav(f, source_sr=sr)
                    #_, embeds, wav_slices = encoder.embed_utterance(wav, return_partials=True)
                    # choose a speaker at random
                    n_speakers = gtruth.count('$') + 1
                    which = np.random.randint(0, n_speakers) 
                    spk_embed = get_speaker_embedding(utt_id, which, encoder)

                    # now relabel the ground truths to three classes... (tss, ntss, ns)
                    labels = np.ones((n, 3))
                    stamp_prev = 0
                    tstamps = tstamps // 10

                    for (stamp, label) in zip(tstamps, gtruth):
                        if label == '':
                            labels[stamp_prev:stamp] = [0, 0, 1]
                        elif label == '$':
                            which -= 1;
                            labels[stamp_prev:stamp] = [0, 0, 1]
                        else:
                            if which == 0: # tss
                                labels[stamp_prev:stamp] = [1, 0, 0]
                            else: # ntss
                                labels[stamp_prev:stamp] = [0, 1, 0]

                        stamp_prev = stamp

                    with open(DEST + folder.name + '/' + utt_id + '.et_vad.fea', 'wb') as f:
                        pickle.dump((logfbanks, spk_embed, labels), f)

                elif MODE == Mode.SET:
                    pass #TODO


# first create the destination directory
if __name__ == '__main__':
    if os.path.exists(DEST):
        if not os.path.isdir(DEST) or os.listdir(DEST):
            print('The specified destination folder is an existing file/directory')
            sys.exit()
    try:
        os.mkdir(DEST)
    except OSError:
        print(f'Could not create destination directory {DEST}')

    # first, load the utterance transcriptions
    text = dict()
    with open(TEXT) as text_file:
        for utterance in text_file:
            utt_id, _, rest = utterance.partition(' ')
            labels, _, tstamps = rest.partition(' ')
            # save them as preprocessed tuples...
            text[utt_id] = (labels.split(','),
                    np.array([int(float(stamp)*1000) for stamp in tstamps.split(' ')], dtype=np.int))

    # extract the features
    features_from_flac(text)