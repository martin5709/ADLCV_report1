import time
from imageclassification import prepare_dataloaders 
from vit import ViT
import torch
import numpy as np
import matplotlib.pyplot as plt
import os
import seaborn as sns
from PIL import Image, ImageFilter

torch.manual_seed(0)
print(os.getcwd())

trainloader, testloader, trainset, testset = prepare_dataloaders(1, classes=[3, 7])

configs = {'image_size':(32,32), 'patch_size':(4,4), 'channels':3, 
         'embed_dim':128, 'num_heads':4, 'num_layers':4, 'num_classes':2,
         'pos_enc':'learnable', 'pool':'cls', 'dropout':0.3, 'fc_dim':None, 
         'num_epochs':20, 'batch_size':16, 'lr':1e-4, 'warmup_steps':625,
         'weight_decay':1e-3, 'gradient_clipping':1}

model = ViT(image_size=configs['image_size'], patch_size=configs['patch_size'], channels=configs['channels'], 
                embed_dim=configs['embed_dim'], num_heads=configs['num_heads'], num_layers=configs['num_layers'],
                pos_enc=configs['pos_enc'], pool=configs['pool'], dropout=configs['dropout'], fc_dim=configs['fc_dim'], 
                num_classes=configs['num_classes'])
model.load_state_dict(torch.load('model.pth'))
count = 0 
with torch.no_grad():
    model.eval()
    for image, label in testloader:
        at = model.half_forward(image)
        num_of_patches = (
            configs["image_size"][0]
            // configs["patch_size"][0]
            * configs["image_size"][1]
            // configs["patch_size"][1]
        )

        

        rollout = torch.eye(at[0].size(-1))
        for block in at:
            #block_fused = block.min(dim=0).values
            #block_fused = block.max(dim=0).values
            block_fused = block.mean(dim=0)

            block_fused += torch.eye(block_fused.size(-1))
            block_fused /= block_fused.sum(dim=-1, keepdim=True)
            rollout = torch.matmul(block_fused, rollout) # Multiplication
        

        ### CLS ATTENTION ###
        cls_attention = rollout[0, 1:]  # Get attention values from [CLS] token to all patches
        cls_attention = cls_attention.reshape(int(np.sqrt(num_of_patches)), int(np.sqrt(num_of_patches)))

        # Normalize the attention map for better visualization
        cls_attention = (cls_attention - cls_attention.min()) / (cls_attention.max() - cls_attention.min())

        cls_attention = 1 - cls_attention

        # Resize and blur the attention map
        cls_attention_resized = Image.fromarray((cls_attention.numpy() * 255).astype(np.uint8)).resize((32, 32), resample=Image.BICUBIC)
        cls_attention_resized = cls_attention_resized.filter(ImageFilter.GaussianBlur(radius=2))
        # Convert the attention map to RGBA
        cls_attention_colored = np.array(cls_attention_resized.convert("L"))
        cls_attention_colored = np.stack([cls_attention_colored]*3 + [cls_attention_colored], axis=-1)
        # Adjust the alpha channel to control brightness
        cls_attention_colored_img = Image.fromarray(cls_attention_colored, mode="RGBA")
        cls_attention_colored_img.putalpha(135)  # Adjust alpha for blending (lower value for darker overlay)

        ### PLOT ###
        fig, axes = plt.subplots(1, 2, figsize=(10, 5))  # Ensure appropriate figure size
        axes[0].imshow((image.squeeze(0).permute(1, 2, 0)+ 1) / 2)
        axes[0].set_xticks([])
        axes[0].set_yticks([])
        axes[0].set_title('Image')
        axes[1].set_aspect("equal")
        ax1 = sns.heatmap(cls_attention_resized, cmap=sns.color_palette("viridis", as_cmap=True), 
                   ax=axes[1], cbar=False)
        axes[1].set_xticks([])
        axes[1].set_yticks([])
        axes[1].set_title('Attention')
        ax1.patch.set_edgecolor('black')  # Set edge color
        ax1.patch.set_linewidth(1.5)  # Set line width

        for spine in axes[1].spines.values():
            spine.set_edgecolor('black')
            spine.set_linewidth(1.5)

        #axes[2].imshow(image.squeeze(0).permute(1, 2, 0), alpha=0.4)
        #axes[2].imshow((cls_attention_colored_img),alpha=0.9)
        #axes[2].set_xticks([])
        #axes[2].set_yticks([])
        #axes[2].set_title('Attention Overlay')
        plt.savefig(f"outputs/{count}.png")
        count += 1
        plt.close()