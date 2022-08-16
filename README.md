# SAM

## Paper information
Rongjunchen Zhang, Tingmin Wu, Sheng Wen, Surya Nepal, Cecile Paris, Yang Xiang

[SAM: Multi-Turn Response Selection Based on Semantic Awareness Matching](https:).

## Abstract

Multi-turn response selection is a key issue in retrieval-based chatbots and has attracted considerable attention in the NLP (Natural Language processing) field. So far, researchers have developed many solutions that can select appropriate responses for multi-turn conversations. However, these works are still suffering from the semantic mismatch problem when responses and context share similar words with different meanings. In this paper, we propose a novel chatbot model based on Semantic Awareness Matching, called SAM. SAM can capture both similarity and semantic features in the context by a two-layer matching network. Appropriate responses are selected according to the matching probability made through the aggregation of the two feature types. In the evaluation, we pick four widely-used datasets and compare SAM's performance to that of twelve other models. Experiment results show that SAM achieves substantial improvements, with up to 1.5% R10@1 on Ubuntu Dialogue Corpus V2, 0.5% R10@1 on Douban Conversation Corpus, and 1.3% R10@1 on E-commerce Corpus.

## Citation

## Download the data
Please download the training required data 
1. [udc.zip](https://drive.google.com/file/d/1asyFD8BZvVAwDbFgIttwjwxhcbGcKmHJ/view?usp=sharing)
2. [BERT_embeddings_original.zip](https://storage.googleapis.com/bert_models/2018_10_18/uncased_L-12_H-768_A-12.zip)
2. [BERT_embeddings_adpted.zip](https://drive.google.com/file/d/1M8V018XZbVDo4Xq96pCLFRt6yVzoKtjH/view)

and unzip them to `data/`

## Train a model

New trained model will be uploaded soon (before 30 July 2022)
