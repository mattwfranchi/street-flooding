# %%
import PIL
from PIL import Image
from tqdm import tqdm
import pandas as pd

import sys 
split = sys.argv[1]

data = pd.read_csv(f"entire_sep29_{split}.csv")

question = 'Does this image show a street flooded with water?'

# make list of len(pe_set.index) with all empty strings 
answers = ['' for i in range(len(data.index))]

# %%

import torch
from transformers import AutoModelForCausalLM
from janus.models import MultiModalityCausalLM, VLChatProcessor
from janus.utils.io import load_pil_images

# specify the path to the model
model_path = "deepseek-ai/Janus-Pro-7B"
vl_chat_processor: VLChatProcessor = VLChatProcessor.from_pretrained(model_path)
tokenizer = vl_chat_processor.tokenizer

vl_gpt: MultiModalityCausalLM = AutoModelForCausalLM.from_pretrained(
    model_path, trust_remote_code=True
)
vl_gpt = vl_gpt.to(torch.bfloat16).cuda().eval()

for i, img in enumerate(tqdm(data['image_path'])):

    conversation = [
        {
            "role": "<|User|>",
            "content": f"<image_placeholder>\n{question}",
            "images": [img],
        },
        {"role": "<|Assistant|>", "content": ""},
    ]

    # load images and prepare for inputs
    prepare_inputs = vl_chat_processor(
        conversations=conversation, images=load_pil_images(conversation), force_batchify=True
    ).to(vl_gpt.device)

    # # run image encoder to get the image embeddings
    inputs_embeds = vl_gpt.prepare_inputs_embeds(**prepare_inputs)

    # # run the model to get the response
    outputs = vl_gpt.language_model.generate(
        inputs_embeds=inputs_embeds,
        attention_mask=prepare_inputs.attention_mask,
        pad_token_id=tokenizer.eos_token_id,
        bos_token_id=tokenizer.bos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        max_new_tokens=2,
        do_sample=False,
        use_cache=True,
    )

    answer = tokenizer.decode(outputs[0].cpu().tolist(), skip_special_tokens=True)
    answers[i] = answer

    if i % 1000 == 0:
        data['answer'] = answers
        data.to_csv(f"entire_sep29_{split}_answers.csv", index=False)

# %%



