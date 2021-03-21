#!/bin/bash

# first, setup the NAME variable
if [ -z ${NAME+x} ]; then
  export NAME=clean # name is empty, default to 'clean'
fi

red=`tput setaf 1`
green=`tput setaf 2`
reset=`tput sgr0`

train_cmd="run.pl"
decode_cmd="run.pl"
musan_root=musan

use_noise=true
use_music=true
use_babble=false

if [ -e $1 ]; then
  echo "Please specifiy the data preparation stage."
  exit 0
else
  stage=$1
fi

if [ ! -d "RIRS_NOISES" ]; then
  # Download and unzip the rirs 
  if [ ! -f "rirs_noises.zip" ]; then
    wget --no-check-certificate http://www.openslr.org/resources/28/rirs_noises.zip
  fi
  unzip rirs_noises.zip
fi

if [ $stage -le 0 ]; then
  echo "${green}Reverberating the dataset...${reset}"
   # Make a version with reverberated speech
  rvb_opts=()
  rvb_opts+=(--rir-set-parameters "0.5, RIRS_NOISES/simulated_rirs/smallroom/rir_list")
  rvb_opts+=(--rir-set-parameters "0.5, RIRS_NOISES/simulated_rirs/mediumroom/rir_list")

  # Reverberate our data folder
  steps/data/reverberate_data_dir.py \
    "${rvb_opts[@]}" \
    --speech-rvb-probability 1 \
    --pointsource-noise-addition-probability 0 \
    --isotropic-noise-addition-probability 0 \
    --num-replications 1 \
    --source-sampling-rate 16000 \
    data/$NAME data/reverb

  # Add a suffix to the reverberated data..
  utils/copy_data_dir.sh --utt-suffix "-reverb" data/reverb data/reverb.new
  rm -rf data/reverb
  mv data/reverb.new data/reverb
fi

if [ $stage -le 1 ]; then
  echo "${green}Augmenting the dataset...${reset}"

  # prepare musan
  steps/data/make_musan.sh --sampling-rate 16000 $musan_root data

  # Get the duration of the MUSAN recordings.  This will be used by the
  # script augment_data_dir.py.
  for name in speech noise music; do
    utils/data/get_utt2dur.sh data/musan_${name}
    mv data/musan_${name}/utt2dur data/musan_${name}/reco2dur
  done

  # noise
  if $use_noise; then
    steps/data/augment_data_dir.py --utt-suffix "noise" --fg-interval 1 --fg-snrs "15:10:5:0" --fg-noise-dir "data/musan_noise" data/$NAME data/noise
  fi
  # music
  if $use_music; then
    steps/data/augment_data_dir.py --utt-suffix "music" --bg-snrs "15:10:8:5" --num-bg-noises "1" --bg-noise-dir "data/musan_music" data/$NAME data/music
  fi
  # speech TODO: can this be used for overlapping speech???
  if $use_babble; then
    steps/data/augment_data_dir.py --utt-suffix "babble" --bg-snrs "20:17:15:13" --num-bg-noises "3:4:5:6:7" --bg-noise-dir "data/musan_speech" data/$NAME data/babble
  fi
fi

# combine the resulted augmented and reverberated scps
combine="data/augmented data/$NAME data/reverb"
if $use_noise; then combine+=" data/noise"; fi
if $use_music; then combine+=" data/music"; fi
if $use_babble; then combine+=" data/babble"; fi
utils/combine_data.sh ${combine}
cp data/$NAME/reco2dur data/augmented
