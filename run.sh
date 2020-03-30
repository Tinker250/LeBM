#!/bin/sh
BERT_BASE_PATH="./data/uncased_L-12_H-768_A-12"
python_path="python"

function train
{
        $python_path -u LeBM.py \
            --task_name=udc \
            --do_train=true \
            --do_eval=false \
            --num_train_epochs=2 \
            --train_batch_size=12 \
            --do_lower_case=True \
            --data_dir=./data/udc \
            --bert_config_file=${BERT_BASE_PATH}/bert_config.json \
            --vocab_file=${BERT_BASE_PATH}/vocab.txt \
            --init_checkpoint=${BERT_BASE_PATH}/bert_model.ckpt \
            --output_dir=./data/output/logic2 \
            --save_steps=1000 \
            --weight_decay=0.01 \
            --max_seq_length=80 \
            --print_steps=1000;
}

function predict
{
        $python_path -u LeBM.py \
            --task_name=udc \
            --do_predict=true \
            --predict_batch_size=12 \
            --data_dir=./data/udc \
            --vocab_file=${BERT_BASE_PATH}/vocab.txt \
            --bert_config_file=${BERT_BASE_PATH}/bert_config.json \
            --init_checkpoint=./data/output/BEST_V2/model.ckpt-166666 \
            --max_seq_length=200 \
            --output_dir=./data/predict/
}

function recall
{
        $python_path -u LeBM.py \
            --task_name=udc \
            --do_recall=true \
            --data_dir=./data/udc \
            --vocab_file=${BERT_BASE_PATH}/vocab.txt \
            --bert_config_file=${BERT_BASE_PATH}/bert_config.json \
            --init_checkpoint=./data/output/BEST_V2/model.ckpt-166666 \
            --max_seq_length=200 \
            --output_dir=./ \
            --pred_file=./data/predict/test_results.tsv \
            --refer_file=./data/udc/test.txt
}
train