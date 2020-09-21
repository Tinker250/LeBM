# LeBM

## Paper information
Rongjunchen Zhang, Tingmin Wu, Sheng Wen, Surya Nepal, Cecile Paris, Yang Xiang

[Left Brain Matching: A Logical Support Network for Multi-Turn Response Selection](https:).

## Abstract

Response selection is a major functionality in a fully automated chatbot, which attracted more and more attention in the filed of natural language processing and machining learning. Existing works concatenate on matching response with highly abstract context vector, which may lead to a logical mismatch when the response and the context have high similarity (e.g., the same word appears in both response and context). In this paper, we propose Left Brain Marching (LeBM), a logical support matching network can select response based on both similarity and logic level.  We evaluate LeBM with both Ubuntu Dialog corpus V1 and V2. The results show the accuracy of our proposed model substantially outperforms the state-of-the-art by 11.4% on Ubuntu Dialog corpus V2.

## Citation

## Download the data
Please download the training required data 
1. [udc.zip](https://drive.google.com/file/d/1Za2av8jFydFhkAWBiCiZenIR6unrlSDF/view)
2. [BERT.zip](https://drive.google.com/file/d/1k-QcbdiGouJ9dX0mrr11dTbBmNYSxDXs/view?usp=sharing)

and unzip them to `data/`

## Train a model

Run the run.sh to start train a new model, all the parameters can be adjusted in run.sh
