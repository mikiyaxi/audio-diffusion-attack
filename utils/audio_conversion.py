import argparse
import io
import logging
import os
import re
import numpy as np
import pandas as pd
from datasets import Dataset, DatasetDict, Features, Image, Value
# from diffusers.pipelines.audio_diffusion import Mel  
from mel import Mel
from tqdm.auto import tqdm
import shutil
from scipy.io.wavfile import write  # For saving audio
from PIL import Image



logging.basicConfig(level=logging.WARN)
logger = logging.getLogger("audio_to_images")


def process_to_disk(input_dir, output_dir, mel):
    examples = []
    # get the list of all files directly in input_dir parameter, since traverse_directies handles recursive call 
    files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
    with tqdm(total=len(files), unit='file', bar_format='{l_bar}{bar}{r_bar}', ascii='->=') as t:
        for file in files:
            if re.search("\.(mp3|wav|m4a)$", file, re.IGNORECASE):
                audio_file = os.path.join(input_dir, file)
                try:
                    mel.load_audio(audio_file)
                except:
                    continue

                for slice in range(mel.get_number_of_slices()):
                    image = mel.audio_slice_to_image(slice)
                    if all(np.frombuffer(image.tobytes(), dtype=np.uint8) == 255):
                        continue
                    with io.BytesIO() as output:
                        image.save(output, format="PNG")
                        bytes = output.getvalue()

                    examples.append(
                        {
                            "image": {"bytes": bytes},
                            "audio_file": audio_file,
                            "slice": slice,
                        }
                    )
            t.update(1)

    if len(examples) == 0:
        return

    ds = Dataset.from_pandas(
        pd.DataFrame(examples),
        features=Features(
            {
                "image": Image(),
                "audio_file": Value(dtype="string"),
                "slice": Value(dtype="int16"),
            }
        ),
    )
    dsd = DatasetDict({"train": ds})
    # you can save to disk for next time use
    # ----------------------------
    dsd.save_to_disk(output_dir)
    # ----------------------------
    # if args.push_to_hub:
    #     dsd.push_to_hub(args.push_to_hub)




# save image file
def process_to_directory(input_dir, output_dir, mel):
    files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
    for file in tqdm(files, desc=f"Processing {input_dir}", unit='file', bar_format='{l_bar}{bar}{r_bar}', ascii='->='):
        if re.search("\.(mp3|wav|m4a)$", file, re.IGNORECASE):
            audio_file = os.path.join(input_dir, file)
            try:
                mel.load_audio(audio_file)
            except:
                continue

            for slice in range(mel.get_number_of_slices()):
                image = mel.audio_slice_to_image(slice)
                if all(np.frombuffer(image.tobytes(), dtype=np.uint8) == 255):
                    continue

                # image format conversion, temporarily line for converting grayscale to RGB
                # remove later when grayscale model is done
                image = image.convert("RGB")

                # adding slices extension here, because when audio file is longer, you need to slice it 
                # and you need to know how many slices are there, and what part is what slice
                # image_filename = os.path.splitext(os.path.basename(audio_file))[0] + f"_slice_{slice}.png"
                image_filename = os.path.splitext(os.path.basename(audio_file))[0] + ".png"
                save_path = os.path.join(output_dir, image_filename)
                image.save(save_path, "PNG")
    return






def process_to_audio(input_dir, output_dir, mel):
    # print(mel.get_sample_rate())
    files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
    for file in tqdm(files, desc=f"Processing {input_dir}", unit='file', bar_format='{l_bar}{bar}{r_bar}', ascii='->='):
        if file.endswith(".png"):
            image_file = os.path.join(input_dir, file)
            
            # Load the image
            image = Image.open(image_file).convert("L")
            
            # Convert the image to audio using the Mel class method
            audio = mel.image_to_audio(image)
            
            # Generate the output audio file name
            audio_filename = os.path.splitext(os.path.basename(image_file))[0] + ".wav"
            save_path = os.path.join(output_dir, audio_filename)
            
            # Save the audio to disk
            write(save_path, mel.get_sample_rate(), audio)




def traverse_directories(root_dir, output_dir, mel, wav=False, save_to_disk=False):
    for root, _, files in os.walk(root_dir):    # _ remove files
        if root == root_dir:  # Skip processing for the parent directory
            continue
        rel_path = os.path.relpath(root, root_dir)
        current_output_dir = os.path.join(output_dir, rel_path)
        os.makedirs(current_output_dir, exist_ok=True)

        if wav:
            process_to_audio(root, current_output_dir, mel)
        elif save_to_disk:
            process_to_disk(root, current_output_dir, mel)
        else:
            process_to_directory(root, current_output_dir, mel)
            separate_images_by_class(current_output_dir)






# split the mixed file based on their class(assuming the first filename is the class name)
# e.g. dog_001.png --> dog/
def separate_images_by_class(src_dir):
    for filename in os.listdir(src_dir):
        if filename.endswith(".png"):
            class_name = filename.split("_")[0]
            dest_dir = os.path.join(src_dir, class_name)
            
            if not os.path.exists(dest_dir):
                os.mkdir(dest_dir)
            
            src_path = os.path.join(src_dir, filename)
            dest_path = os.path.join(dest_dir, filename)
            
            shutil.move(src_path, dest_path)



def main(args):

    if args.wav:
        print("###########################################")
        print("#                                         #")
        print("#  Mel-Spectrogram to Audio Conversion..  #")
        print("#                                         #")
        print("###########################################")

    else:
        print("###########################################")
        print("#                                         #")
        print("#  Audio to Mel-Spectrogram Conversion..  #")
        print("#                                         #")
        print("###########################################")


    # initalized Mel object
    mel = Mel(
        x_res=args.resolution[0],
        y_res=args.resolution[1],
        hop_length=args.hop_length,
        sample_rate=args.sample_rate,
        n_fft=args.n_fft,
    )
    # traverse method handle nested directories
    if args.parent_dir:
        traverse_directories(args.parent_dir, args.output_dir, mel, wav=args.wav, save_to_disk=args.save_to_disk)
    
    # when "--input_dir" argument is received
    else:
        os.makedirs(args.output_dir, exist_ok=True)
        if args.wav:
            process_to_audio(args.input_dir, args.output_dir, mel)
            return 
        elif args.save_to_disk:
            process_to_disk(args.input_dir, args.output_dir, mel)
            return 
        else:
            process_to_directory(args.input_dir, args.output_dir, mel)
            separate_images_by_class(args.output_dir)
            return 
    # print("use --parent_dir")





if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create dataset of Mel spectrograms from directory of audio files.")
    parser.add_argument("--wav", action='store_true')
    parser.add_argument("--input_dir", type=str)
    parser.add_argument("--parent_dir", type=str)
    parser.add_argument("--output_dir", type=str, default="data")
    parser.add_argument("--save_to_disk", type=bool, default=False)
    parser.add_argument(
        "--resolution",
        type=str,
        default="256",
        help="Either square resolution or width,height.",
    )
    parser.add_argument("--hop_length", type=int, default=512)
    # parser.add_argument("--push_to_hub", type=str, default=None)
    # parser.add_argument("--hop_length", type=int, default=1024)
    parser.add_argument("--sample_rate", type=int, default=16000)
    # parser.add_argument("--sample_rate", type=int, default=22050)
    parser.add_argument("--n_fft", type=int, default=2048)
    
    args = parser.parse_args()
    
    if args.input_dir is None and args.parent_dir is None:
        raise ValueError("You must specify either an input directory or an input parent directory for the audio files.")
    
    try:
        args.resolution = (int(args.resolution), int(args.resolution))
    except ValueError:
        try:
            args.resolution = tuple(int(x) for x in args.resolution.split(","))
            if len(args.resolution) != 2:
                raise ValueError
        except ValueError:
            raise ValueError("Resolution must be a tuple of two integers or a single integer.")
    
    assert isinstance(args.resolution, tuple)
    
    main(args)