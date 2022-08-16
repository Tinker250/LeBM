#!/bin/sh
BERT_BASE_PATH="./data/uncased_L-12_H-768_A-12_adapted"
python_path="python"

function train
{
        $python_path -u SAM.py \
            --task_name=udc \
            --do_train=true \
            --do_eval=false \
            --num_train_epochs=3 \
            --train_batch_size=20 \
            --do_lower_case=True \
            --data_dir=./data/udc \
            --bert_config_file=${BERT_BASE_PATH}/bert_config.json \
            --vocab_file=${BERT_BASE_PATH}/vocab.txt \
            --init_checkpoint=${BERT_BASE_PATH}/bert_model.ckpt \
            --output_dir=./data/output/SAM_V3 \
            --save_steps=2000 \
            --weight_decay=0.01 \
            --max_seq_length=200 \
            --print_steps=2000;
}

function predict
{
        $python_path -u SAM.py \
            --task_name=udc \
            --do_predict=true \
            --predict_batch_size=100 \
            --data_dir=./data/udc \
            --vocab_file=${BERT_BASE_PATH}/vocab.txt \
            --bert_config_file=${BERT_BASE_PATH}/bert_config.json \
            --init_checkpoint=./data/output/V2/model.ckpt-406000 \
            --max_seq_length=210 \
            --output_dir=./data/predict/
}

function recall
{
        $python_path -u SAM.py \
            --task_name=udc \
            --do_recall=true \
            --data_dir=./data/udc \
            --vocab_file=${BERT_BASE_PATH}/vocab.txt \
            --bert_config_file=${BERT_BASE_PATH}/bert_config.json \
            --init_checkpoint=./data/output/len_210/model.ckpt-final \
            --max_seq_length=210 \
            --output_dir=./ \
            --pred_file=./data/predict/test_results.tsv \
            --refer_file=./data/udc/test.txt
}

train
