"""Extracts and saves speaker embedding vectors for each speaker in the LibriSpeech dataset.
"""

import numpy as np
import os
import soundfile as sf
from glob import glob
from resemblyzer import VoiceEncoder, preprocess_wav, normalize_volume
from kaldiio import WriteHelper

LIBRI_SOURCE = 'LibriSpeech/'
DIRECTORIES = ['dev-clean']#, 'dev-other', 'test-clean', 'test-other']
               #'train-clean-100', 'train-clean-360'],
               #'train-other-500']
EMBED_OUT = 'embeddings/'
DEST = 'embeddings'

SAVE_SCP = True
DVECTORS = True
XVECTORS = True
N_WAVS = 2

encoder = VoiceEncoder()

if DVECTORS:
    dvector_writer = WriteHelper(f'ark,scp:{DEST}/dvectors.ark,{DEST}/dvectors.scp')

for directory in DIRECTORIES:
    print(f"Processing directory: {directory}")
    with os.scandir(LIBRI_SOURCE + directory) as speakers:
        for speaker in speakers:
            print(f"Processing speaker: {speaker.name}")
            if not os.path.isdir(speaker.path): continue

            with os.scandir(speaker.path) as sessions:
                sessions = list(sessions)
                # select a random session
                session = sessions[np.random.randint(0, len(sessions))]

                # get the files for the current speaker
                files = glob(session.path + '/*.flac')
                n_files = len(files)
                wavs = []
                for i in range(N_WAVS):
                    random_file = files[np.random.randint(0, n_files)]
                    wavs.append(preprocess_wav(sf.read(random_file)[0]))

                # extract the embedding
                dvector = encoder.embed_speaker(wavs)

                # save the embedding
                if SAVE_SCP:
                    if DVECTORS:
                        dvector_writer(speaker.name, dvector)
                else:
                    np.save(EMBED_OUT + speaker.name + '.dvector', dvector)

if DVECTORS:
    dvector_writer.close()
