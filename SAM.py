from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import csv
import os
import modeling
import optimization
import tokenization
import tensorflow as tf
import numpy as np
import tqdm
from sklearn.feature_extraction.text import TfidfVectorizer
import re
from tensorflow.compat.v1 import ConfigProto
from tensorflow.compat.v1 import InteractiveSession

# gpus = tf.config.experimental.list_physical_devices('GPU')
# tf.config.experimental.set_memory_growth(gpus[1], True)
# tf.config.experimental.set_virtual_device_configuration(
#         gpus[0],
#         [tf.config.experimental.VirtualDeviceConfiguration(memory_limit=7000)])
# config1=tf.ConfigProto(gpu_options=gpu_options)
# session = tf.Session(config=config1)
# tf.compat.v1.disable_eager_execution()
# tf.config.gpu.set_per_process_memory_growth(True)
flags = tf.flags

FLAGS = flags.FLAGS

## Required parameters
flags.DEFINE_string(
    "data_dir", None,
    "The input data dir. Should contain the .tsv files (or other data files) "
    "for the task.")

flags.DEFINE_string(
    "bert_config_file", None,
    "The config json file corresponding to the pre-trained BERT model. "
    "This specifies the model architecture.")

flags.DEFINE_string("task_name", None, "The name of the task to train.")

flags.DEFINE_string("vocab_file", None,
                    "The vocabulary file that the BERT model was trained on.")

flags.DEFINE_string(
    "output_dir", None,
    "The output directory where the model checkpoints will be written.")

## Other parameters

flags.DEFINE_string(
    "init_checkpoint", None,
    "Initial checkpoint (usually from a pre-trained BERT model).")

flags.DEFINE_bool(
    "do_lower_case", True,
    "Whether to lower case the input text. Should be True for uncased "
    "models and False for cased models.")

flags.DEFINE_integer(
    "max_seq_length", 128,
    "The maximum total input sequence length after WordPiece tokenization. "
    "Sequences longer than this will be truncated, and sequences shorter "
    "than this will be padded.")

flags.DEFINE_bool("do_train", False, "Whether to run training.")

flags.DEFINE_bool("do_eval", False, "Whether to run eval on the dev set.")

flags.DEFINE_bool("do_recall", False, "Whether to run recall on the prediction result.")

flags.DEFINE_bool(
    "do_predict", False,
    "Whether to run the model in inference mode on the test set.")

flags.DEFINE_integer("train_batch_size", 12, "Total batch size for training.")

flags.DEFINE_integer("eval_batch_size", 12, "Total batch size for eval.")

flags.DEFINE_integer("predict_batch_size", 12, "Total batch size for predict.")

flags.DEFINE_float("learning_rate", 5e-5, "The initial learning rate for Adam.")

flags.DEFINE_float("num_train_epochs", 3.0,
                   "Total number of training epochs to perform.")

flags.DEFINE_float(
    "warmup_proportion", 0.1,
    "Proportion of training to perform linear learning rate warmup for. "
    "E.g., 0.1 = 10% of training.")

flags.DEFINE_integer("save_checkpoints_steps", 1000,
                     "How often to save the model checkpoint.")

flags.DEFINE_integer("iterations_per_loop", 1000,
                     "How many steps to make in each estimator call.")

flags.DEFINE_bool("use_tpu", False, "Whether to use TPU or GPU/CPU.")

tf.flags.DEFINE_string(
    "tpu_name", None,
    "The Cloud TPU to use for training. This should be either the name "
    "used when creating the Cloud TPU, or a grpc://ip.address.of.tpu:8470 "
    "url.")

tf.flags.DEFINE_string(
    "tpu_zone", None,
    "[Optional] GCE zone where the Cloud TPU is located in. If not "
    "specified, we will attempt to automatically detect the GCE project from "
    "metadata.")

tf.flags.DEFINE_string(
    "gcp_project", None,
    "[Optional] Project name for the Cloud TPU-enabled project. If not "
    "specified, we will attempt to automatically detect the GCE project from "
    "metadata.")

tf.flags.DEFINE_string("master", None, "[Optional] TensorFlow master URL.")

flags.DEFINE_integer(
    "num_tpu_cores", 8,
    "Only used if `use_tpu` is True. Total number of TPU cores to use.")

flags.DEFINE_string("pred_file", None, "[Optional] Prediction result file when do recall")
flags.DEFINE_string("refer_file", None, "[Optional] Prediction reference file when do recall")
flags.DEFINE_bool("retrain", True, "[Optional] Rewrite the train file to train.tf_record")


class InputExample(object):
  """A single training/test example for simple sequence classification."""

  def __init__(self, guid, text_a, text_b=None, label=None):
    """Constructs a InputExample.

    Args:
      guid: Unique id for the example.
      text_a: string. The untokenized text of the first sequence. For single
        sequence tasks, only this sequence must be specified.
      text_b: (Optional) string. The untokenized text of the second sequence.
        Only must be specified for sequence pair tasks.
      label: (Optional) string. The label of the example. This should be
        specified for train and dev examples, but not for test examples.
    """
    self.guid = guid
    self.text_a = text_a
    self.text_b = text_b
    self.label = label


class PaddingInputExample(object):
  """Fake example so the num input examples is a multiple of the batch size.

  When running eval/predict on the TPU, we need to pad the number of examples
  to be a multiple of the batch size, because the TPU requires a fixed batch
  size. The alternative is to drop the last batch, which is bad because it means
  the entire output data won't be generated.

  We use this class instead of `None` because treating `None` as padding
  battches could cause silent errors.
  """


class InputFeatures(object):
  """A single set of features of data."""

  def __init__(self,
               input_ids,
               input_mask,
               segment_ids,
               label_id,
               is_real_example=True):
    self.input_ids = input_ids
    self.input_mask = input_mask
    self.segment_ids = segment_ids
    self.label_id = label_id
    self.is_real_example = is_real_example


class DataProcessor(object):
  """Base class for data converters for sequence classification data sets."""

  def get_train_examples(self, data_dir):
    """Gets a collection of `InputExample`s for the train set."""
    raise NotImplementedError()

  def get_dev_examples(self, data_dir):
    """Gets a collection of `InputExample`s for the dev set."""
    raise NotImplementedError()

  def get_test_examples(self, data_dir):
    """Gets a collection of `InputExample`s for prediction."""
    raise NotImplementedError()

  def get_labels(self):
    """Gets the list of labels for this data set."""
    raise NotImplementedError()

  @classmethod
  def _read_tsv(cls, input_file, quotechar=None):
    """Reads a tab separated value file."""
    with tf.gfile.Open(input_file, "r") as f:
      reader = csv.reader(f, delimiter="\t", quotechar=quotechar)
      lines = []
      for line in reader:
        lines.append(line)
      return lines

class UDCProcessor(DataProcessor): 
    """Processor for the UDC data set."""
    def _create_examples(self, lines, set_type): 
        """Creates examples for the training and dev sets."""
        examples = []
        print("UDC dataset is too big, loading data spent a long time, please wait patiently..................")
        for (i, line) in enumerate(lines): 
            if len(line) < 3: 
                print("data format error: %s" % "\t".join(line))
                print("data row contains at least three parts: label\tconv1\t.....\tresponse")
                continue
            guid = "%s-%d" % (set_type, i)
            # text_a = " __eot__ ".join(line[1: -1])
            text_a = line[0]
            # for sentence in temp:
            #   text_a.append(tokenization.convert_to_unicode(sentence))
            text_a = tokenization.convert_to_unicode(text_a)
            # text_a = text_a.split('\t')
            text_b = line[1]
            text_b = tokenization.convert_to_unicode(text_b)
            label = line[-1]
            label = tokenization.convert_to_unicode(label)
            examples.append(
                InputExample(
                    guid=guid, text_a=text_a, text_b=text_b, label=label))
        return examples

    def get_train_examples(self, data_dir): 
        """See base class."""
        examples = []
        lines = self._read_tsv(os.path.join(data_dir, "train_v2.txt"))
        examples = self._create_examples(lines, "train")
        return examples

    def get_dev_examples(self, data_dir): 
        """See base class."""
        examples = []
        lines = self._read_tsv(os.path.join(data_dir, "valid_v2.txt"))
        examples = self._create_examples(lines, "dev")
        return examples

    def get_test_examples(self, data_dir): 
        """See base class."""
        examples = []
        lines = self._read_tsv(os.path.join(data_dir, "test_v2.txt"))
        examples = self._create_examples(lines, "test")
        return examples

    @staticmethod
    def get_labels(): 
        """See base class."""
        return ["0", "1"]

class EvalUDC(object): 
    """
    evaluate udc
    """
    def __init__(self, pred, refer): 
        """
        predict file
        """
        self.pred_file = pred
        self.refer_file = refer

    def load_data(self): 
        """
        load reference label and predict label
        """
        data = [] 
        refer_label = []
        with open(self.refer_file, 'r') as fr: 
            for line in fr: 
                label = line.rstrip('\n').split('\t')[0]
                refer_label.append(label)
        idx = 0
        with open(self.pred_file, 'r') as fr: 
            for line in fr: 
                elems = line.rstrip('\n').split('\t')
                if len(elems) != 2: 
                    continue
                match_prob = elems[1]
                data.append((float(match_prob), int(refer_label[idx])))
                idx += 1
        return data

    def get_p_at_n_in_m(self, data, n, m, ind):
        """
        calculate precision in recall n
        """
        pos_score = data[ind][0]
        curr = data[ind: ind + m]
        curr = sorted(curr, key = lambda x: x[0], reverse = True)

        if curr[n - 1][0] <= pos_score:
            return 1
        return 0

    def evaluate(self):
        """
        calculate udc data
        """
        data = self.load_data()
        # print(data)
        assert len(data) % 10 == 0
        
        p_at_1_in_2 = 0.0
        p_at_1_in_10 = 0.0
        p_at_2_in_10 = 0.0
        p_at_5_in_10 = 0.0

        length = len(data)/10
        length = int(length)

        for i in range(0, length):
            ind = i * 10
            assert data[ind][1] == 1
    
            p_at_1_in_2 += self.get_p_at_n_in_m(data, 1, 2, ind)
            p_at_1_in_10 += self.get_p_at_n_in_m(data, 1, 10, ind)
            p_at_2_in_10 += self.get_p_at_n_in_m(data, 2, 10, ind)
            p_at_5_in_10 += self.get_p_at_n_in_m(data, 5, 10, ind)

        metrics_out = [p_at_1_in_2 / length, p_at_1_in_10 / length, \
                p_at_2_in_10 / length, p_at_5_in_10 / length]
        return metrics_out

def add_inner_sep(texts,is_text_b):
  return_text = ""
  if isinstance(texts, list):
    for i, text in enumerate(texts):
      text = re.sub('__eot__','unused0',text)
      text = re.sub('__eou__','unused1',text)
      return_text += text
  else:
    text = texts
    text = re.sub('__eot__','unused0',text)
    text = re.sub('__eou__','unused1',text)
    return_text += text
  return return_text
    

def convert_single_example(ex_index, example, label_list, max_seq_length,
                           tokenizer):
  """Converts a single `InputExample` into a single `InputFeatures`."""

  if isinstance(example, PaddingInputExample):
    return InputFeatures(
        input_ids=[0] * max_seq_length,
        input_mask=[0] * max_seq_length,
        segment_ids=[0] * max_seq_length,
        label_id=0,
        is_real_example=False)

  label_map = {}
  for (i, label) in enumerate(label_list):
    label_map[label] = i

  # word2index, scores = TFIDF_Builder(example)

  # text_a,text_b = _truncate_seq_pair(example.text_a, example.text_b, max_seq_length, word2index,scores)
  # text_a = " ".join([str(x) for x in text_a])
  # text_b = " ".join([str(x) for x in text_b])

  # print("*********************")
  # print(example.text_a)
  # print(kkkk)

  text_a = add_inner_sep(example.text_a,False)
  text_b = add_inner_sep(example.text_b,True)
  
  tokens_a = tokenizer.tokenize(text_a)
  tokens_b = None
  if example.text_b:
    tokens_b = tokenizer.tokenize(text_b)

  if tokens_b:
    # word2index, scores = TFIDF_Builder(tokens_a,tokens_b)
    # tokens_a,tokens_b = _truncate_seq_pair(tokens_a, tokens_b, max_seq_length-3, word2index,score)

    normalization_tokens(tokens_a, tokens_b, max_seq_length - 3)
  else:
    # Account for [CLS] and [SEP] with "- 2"
    if len(tokens_a) > max_seq_length - 2:
      tokens_a = tokens_a[0:(max_seq_length - 2)]

  # print(len(tokens_a)+len(tokens_b))
  # print(kkk)
  
  # The convention in BERT is:
  # (a) For sequence pairs:
  #  tokens:   [CLS] is this jack ##son ##ville ? [SEP] no it is not . [SEP]
  #  type_ids: 0     0  0    0    0     0       0 0     1  1  1  1   1 1
  # (b) For single sequences:
  #  tokens:   [CLS] the dog is hairy . [SEP]
  #  type_ids: 0     0   0   0  0     0 0
  #
  # Where "type_ids" are used to indicate whether this is the first
  # sequence or the second sequence. The embedding vectors for `type=0` and
  # `type=1` were learned during pre-training and are added to the wordpiece
  # embedding vector (and position vector). This is not *strictly* necessary
  # since the [SEP] token unambiguously separates the sequences, but it makes
  # it easier for the model to learn the concept of sequences.
  #
  # For classification tasks, the first vector (corresponding to [CLS]) is
  # used as the "sentence vector". Note that this only makes sense because
  # the entire model is fine-tuned.
  tokens = []
  segment_ids = []
  tokens.append("[CLS]")
  segment_ids.append(0)
  for token in tokens_a:
    tokens.append(token)
    segment_ids.append(0)
  tokens.append("[SEP]")
  segment_ids.append(0)

  # token_b_index = [len(tokens)-1]

  if tokens_b:
    for token in tokens_b:
      tokens.append(token)
      segment_ids.append(1)
    tokens.append("[SEP]")
    segment_ids.append(1)
  
  input_ids = tokenizer.convert_tokens_to_ids(tokens)

  # The mask has 1 for real tokens and 0 for padding tokens. Only real
  # tokens are attended to.
  input_mask = [1] * len(input_ids)

  # Zero-pad up to the sequence length.
  while len(input_ids) < max_seq_length:
    input_ids.append(0)
    input_mask.append(0)
    segment_ids.append(1)

  assert len(input_ids) == max_seq_length
  assert len(input_mask) == max_seq_length
  assert len(segment_ids) == max_seq_length

  label_id = label_map[example.label]
  if(label_id == 0):
    label_id = [int(0)] #TODO filter size
  elif(label_id == 1):
    label_id = [int(1)] #TODO filter size

  
  if ex_index < 5:
    tf.logging.info("*** Example ***")
    tf.logging.info("guid: %s" % (example.guid))
    tf.logging.info("tokens: %s" % " ".join(
        [tokenization.printable_text(x) for x in tokens]))
    tf.logging.info("input_ids: %s" % " ".join([str(x) for x in input_ids]))
    tf.logging.info("input_mask: %s" % " ".join([str(x) for x in input_mask]))
    tf.logging.info("segment_ids: %s" % " ".join([str(x) for x in segment_ids]))
    tf.logging.info("label: %s (id = %s)" % (example.label, " ".join([str(x) for x in label_id])))

  feature = InputFeatures(
      input_ids=input_ids,
      input_mask=input_mask,
      segment_ids=segment_ids,
      label_id=label_id,
      is_real_example=True)
  return feature

def file_based_convert_examples_to_features(
    examples, label_list, max_seq_length, tokenizer, output_file):
  """Convert a set of `InputExample`s to a TFRecord file."""

  writer = tf.python_io.TFRecordWriter(output_file)
  # word2index,scores = TFIDF_Builder(examples,tokenizer)

  for (ex_index, example) in enumerate(examples):
    if(not FLAGS.retrain):
      break
    if ex_index % 10000 == 0:
      tf.logging.info("Writing example %d of %d" % (ex_index, len(examples)))

    feature = convert_single_example(ex_index, example, label_list,
                                     max_seq_length, tokenizer)

    def create_int_feature(values):
      f = tf.train.Feature(int64_list=tf.train.Int64List(value=list(values)))
      return f

    features = collections.OrderedDict()
    features["input_ids"] = create_int_feature(feature.input_ids)
    features["input_mask"] = create_int_feature(feature.input_mask)
    features["segment_ids"] = create_int_feature(feature.segment_ids)
    features["label_ids"] = create_int_feature(feature.label_id)
    features["is_real_example"] = create_int_feature(
        [int(feature.is_real_example)])

    tf_example = tf.train.Example(features=tf.train.Features(feature=features))
    writer.write(tf_example.SerializeToString())
  writer.close()


def file_based_input_fn_builder(input_file, seq_length, is_training,
                                drop_remainder):
  """Creates an `input_fn` closure to be passed to TPUEstimator."""
  name_to_features = {
      "input_ids": tf.FixedLenFeature([seq_length], tf.int64),
      "input_mask": tf.FixedLenFeature([seq_length], tf.int64),
      "segment_ids": tf.FixedLenFeature([seq_length], tf.int64),
      "label_ids": tf.FixedLenFeature([], tf.int64), #TODO filter size
      "is_real_example": tf.FixedLenFeature([], tf.int64),
  }

  def _decode_record(record, name_to_features):
    """Decodes a record to a TensorFlow example."""
    example = tf.parse_single_example(record, name_to_features)

    # tf.Example only supports tf.int64, but the TPU only supports tf.int32.
    # So cast all int64 to int32.
    for name in list(example.keys()):
      t = example[name]
      if t.dtype == tf.int64:
        t = tf.to_int32(t)
      example[name] = t

    return example

  def input_fn(params):
    """The actual input function."""
    batch_size = params["batch_size"]

    # For training, we want a lot of parallel reading and shuffling.
    # For eval, we want no shuffling and parallel reading doesn't matter.
    d = tf.data.TFRecordDataset(input_file)
    if is_training:
      d = d.repeat()
      d = d.shuffle(buffer_size=100)

    d = d.apply(
        tf.contrib.data.map_and_batch(
            lambda record: _decode_record(record, name_to_features),
            batch_size=batch_size,
            drop_remainder=drop_remainder))

    return d

  return input_fn


def _truncate_seq_pair(tokens_a, tokens_b, max_length, word2index, scores):
  scores = np.reshape(scores,[scores.shape[1],1])
  scores = scores.toarray()
  all_scores = {}
  all_index = 0
  text_a = ""
  text_b = ""
  for token in tokens_a:
    text_a += token+" "
  text_a = text_a[:-1]
  for token in tokens_b:
    text_b += token+" "
  text_b = text_b[:-1]
  
  dialog = []
  dialog_t = text_a.split('[unused0]')
  while ''in dialog_t:
      dialog_t.remove('')
  for i,sentence in enumerate(dialog_t):
    if(i != len(dialog_t)-1):
      dialog.append(sentence+" [unused0]")
    else:
      dialog.append(sentence+" [unused0] [token_sep] ")
  dialog.append(text_b)
  for i in range(0,len(dialog)):
    temp = dialog[i]
    temp = temp.split(' ')
    while '' in temp:
      temp.remove('')

    for j,word in enumerate(temp):
      if(word == "[unused0]" or word == "[unused1]" or word == "[unused2]" or word == "[token_sep]"):
        all_scores[str(all_index)] = 10
      elif(word in word2index.keys()):
        all_scores[str(all_index)] = scores[word2index[word]]
      else:
        all_scores[str(all_index)] = -1
      all_index += 1
  # print(len(all_scores))
  all_scores = sorted(all_scores.items(),key=lambda item:item[1])
  delete_order = []    
    # print(all_scores)
  for score in all_scores:
      delete_order.append(int(score[0]))
  flatten_dialog = ""
  for u in dialog:
    flatten_dialog += u

  flatten_dialog = flatten_dialog.split(' ')
  while ''in flatten_dialog:
    flatten_dialog.remove('')
  # print(len(flatten_dialog))
  total_length = len(flatten_dialog)
  delete_index = 0
  while True:
    # print(delete_order[delete_index])
    if(total_length <= max_length+1):
        break
    else:
        flatten_dialog[delete_order[delete_index]] = 0
        total_length -= 1
        delete_index += 1

  selected_token = ""
  for token in flatten_dialog:
    if(token != 0):
      selected_token += token+' '
  selected_token = selected_token[:-1]
  # print(selected_token)
              
  sentences = selected_token.split('[token_sep]')
  selected_token_b = sentences[-1].split(' ')
  selected_token_a = sentences[0].split(' ')
  while ''in selected_token_a:
    selected_token_a.remove('')
  while ''in selected_token_b:
    selected_token_b.remove('')
  # print(selected_token_a)
  # print(selected_token_b)
  # print(len(selected_token_a)+len(selected_token_b))
  # print(kkk)

  return selected_token_a,selected_token_b

def normalization_tokens(tokens_a,tokens_b,max_length):
  while True:
    total_length = len(tokens_a) + len(tokens_b)
    if total_length <= max_length:
      break
    if len(tokens_a) > len(tokens_b):
      tokens_a.pop(0)
    else:
      tokens_b.pop(0)


def create_model(bert_config, is_training, input_ids, input_mask, segment_ids,
                 labels, num_labels, use_one_hot_embeddings,batch_size):
  """Creates a classification model."""
  model = modeling.BertModel(
      config=bert_config,
      is_training=is_training,
      input_ids=input_ids,
      input_mask=input_mask,
      token_type_ids=segment_ids,
      use_one_hot_embeddings=use_one_hot_embeddings)

  # In the demo, we are doing a simple classification task on the entire
  # segment.
  #
  # If you want to use the token-level output, use model.get_sequence_output()
  # instead.
  output_layer_1 = model.get_pooled_output()
  output_layer_2 = model.get_sequence_output()

  output_layer_1 = tf.nn.dropout(output_layer_1, keep_prob=0.9)
  output_layer_2 = tf.nn.dropout(output_layer_2, keep_prob=0.9)

  dense_layer_1 = tf.keras.layers.Dense(2)
  dense_output_1 = dense_layer_1(output_layer_1)
  print("*******************output_layer shape********************")
  print(dense_output_1.shape)
  print(output_layer_2.shape)
  convlution_layer_1 = tf.compat.v1.keras.layers.Conv1D(100,11,activation='relu',strides=2)
  convlution_output_1 = convlution_layer_1(output_layer_2)
  convlution_layer_2 = tf.compat.v1.keras.layers.Conv1D(100,11,activation='relu',strides=2)
  convlution_output_2 = convlution_layer_2(convlution_output_1)
  pool_1 = tf.compat.v1.keras.layers.MaxPool1D(2,2,padding='valid')
  pool_1_output = pool_1(convlution_output_2)
  print(pool_1_output.shape)
  convlution_layer_3 = tf.compat.v1.keras.layers.Conv1D(50,11,activation='relu',strides=2)
  convlution_output_3 = convlution_layer_3(convlution_output_2)
  convlution_layer_4 = tf.compat.v1.keras.layers.Conv1D(50,17,activation='relu',strides=1)
  print(convlution_output_1.shape)
  print(convlution_output_2.shape)
  print(convlution_output_3.shape)
  convlution_output_4 = convlution_layer_4(convlution_output_3)
  print(convlution_output_4.shape)
  # convlution_layer_5 = tf.compat.v1.keras.layers.Conv1D(100,9,activation='relu',strides=1)
  # convlution_output_5 = convlution_layer_5(convlution_output_4)
  # print(convlution_output_5.shape)
  convlution_output_4 = tf.reshape(convlution_output_4,[batch_size,50])
  
  # print(token_b_index.shape)
  # output_token_a = output_layer_2[:,:100,:]
  # print(output_token_a.shape)
  # output_token_b = output_layer_2[:,100:,:]
  # lstm_layer_1 = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(150))
  # lstm_out = lstm_layer_1(output_layer_2)
  # lstm_layer_2 = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(100))
  # lstm_out_token_b = lstm_layer_2(output_token_b)

  # logic_output = tf.matmul(lstm_out_token_a,lstm_out_token_b)

  dense_layer_2 = tf.keras.layers.Dense(2)
  dense_output_2 = dense_layer_2(convlution_output_4)

  # final = tf.keras.layers.concatenate([dense_output_1,dense_output_2],-1)
  final =  dense_output_1+dense_output_2

  with tf.variable_scope("loss"):
    # if is_training:
      # I.e., 0.1 dropout
      # con_layer3 = tf.nn.dropout(con_layer4, keep_prob=0.8)

    # logits = tf.matmul(lstm_output, output_weights, transpose_b=True)
    # logits = tf.nn.bias_add(logits, output_bias)
    logits = final
    probabilities = tf.nn.softmax(logits, axis=-1)
    log_probs = tf.nn.log_softmax(logits, axis=-1)
    print("*******probabilities layer shape********")
    print(probabilities.shape)
    one_hot_labels = tf.one_hot(labels, depth=2, dtype=tf.float32)
    # print("*******one_hot_labels layer shape********")
    # print(one_hot_labels.shape,labels.shape)
    # f_label = tf.compat.v1.reshape(labels,[12,1])
    # print("*******log_probs layer shape********")
    # print(labels.shape)
    per_example_loss = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=labels,logits=logits)
    # per_example_loss = -tf.reduce_sum(one_hot_labels * log_probs, axis=-1)
    loss = tf.reduce_mean(per_example_loss)
    return (loss, per_example_loss, logits, probabilities,dense_output_1,dense_output_2)


def model_fn_builder(bert_config, num_labels, init_checkpoint, learning_rate,
                     num_train_steps, num_warmup_steps, use_tpu,
                     use_one_hot_embeddings,batch_size):
  """Returns `model_fn` closure for TPUEstimator."""

  def model_fn(features, labels, mode, params):  # pylint: disable=unused-argument
    """The `model_fn` for TPUEstimator."""

    tf.logging.info("*** Features ***")
    for name in sorted(features.keys()):
      tf.logging.info("  name = %s, shape = %s" % (name, features[name].shape))

    input_ids = features["input_ids"]
    input_mask = features["input_mask"]
    segment_ids = features["segment_ids"]
    # token_b_index = features["token_b_index"]
    label_ids = features["label_ids"]
    is_real_example = None
    if "is_real_example" in features:
      is_real_example = tf.cast(features["is_real_example"], dtype=tf.float32)
    else:
      is_real_example = tf.ones(tf.shape(label_ids), dtype=tf.float32)

    is_training = (mode == tf.estimator.ModeKeys.TRAIN)

    (total_loss, per_example_loss, logits, probabilities,dense_output_1,dense_output_2) = create_model(
        bert_config, is_training, input_ids, input_mask, segment_ids, label_ids,
        num_labels, use_one_hot_embeddings,batch_size)

    tvars = tf.trainable_variables()
    initialized_variable_names = {}
    scaffold_fn = None
    if init_checkpoint:
      (assignment_map, initialized_variable_names
      ) = modeling.get_assignment_map_from_checkpoint(tvars, init_checkpoint)
      if use_tpu:

        def tpu_scaffold():
          tf.train.init_from_checkpoint(init_checkpoint, assignment_map)
          return tf.train.Scaffold()

        scaffold_fn = tpu_scaffold
      else:
        tf.train.init_from_checkpoint(init_checkpoint, assignment_map)

    # tf.logging.info("**** Trainable Variables ****")
    # for var in tvars:
    #   init_string = ""
    #   if var.name in initialized_variable_names:
    #     init_string = ", *INIT_FROM_CKPT*"
    #   tf.logging.info("  name = %s, shape = %s%s", var.name, var.shape,
    #                   init_string)

    output_spec = None
    if mode == tf.estimator.ModeKeys.TRAIN:

      train_op = optimization.create_optimizer(
          total_loss, learning_rate, num_train_steps, num_warmup_steps, use_tpu)

      output_spec = tf.compat.v1.estimator.EstimatorSpec(
          mode=mode,
          loss=total_loss,
          train_op=train_op)
    elif mode == tf.estimator.ModeKeys.EVAL:

      def metric_fn(per_example_loss, label_ids, logits, is_real_example):
        predictions = tf.argmax(logits, axis=-1, output_type=tf.int32)
        accuracy = tf.metrics.accuracy(
            labels=label_ids, predictions=predictions, weights=is_real_example)
        loss = tf.metrics.mean(values=per_example_loss, weights=is_real_example)
        return {
            "eval_accuracy": accuracy,
            "eval_loss": loss,
        }

      eval_metrics = (metric_fn,
                      [per_example_loss, label_ids, logits, is_real_example])
      output_spec = tf.compat.v1.estimator.EstimatorSpec(
          mode=mode,
          loss=total_loss,
          eval_metrics=eval_metrics)
    else:
      output_spec = tf.compat.v1.estimator.EstimatorSpec(
          mode=mode,
          # predictions={"probabilities": probabilities,"similarity":dense_output_1,"logic":dense_output_2},
          predictions={"probabilities":probabilities}
          )
    return output_spec

  return model_fn

def TFIDF_Builder(examples,tokenizer):
  print("begin TFIDF")
  temp = []
  for i,example in enumerate(examples):
    if(i % 20000 == 0):
      print(i/len(examples))
    text_a = add_inner_sep(example.text_a,False)
    text_b = add_inner_sep(example.text_b,True)
    tokens_a = tokenizer.tokenize(text_a)
    tokens_b = tokenizer.tokenize(text_b)
    text_a = " ".join(x for x in tokens_a)
    text_b = " ".join(x for x in tokens_b)

    temp.append(text_a[:-1]+" "+text_b[:-1])

  vectorizer = TfidfVectorizer()
  scores = vectorizer.fit_transform(temp)
  features = vectorizer.get_feature_names()
  word2index = {}
  for i,feature in enumerate(features):
    if(i%100 == 0):
      print(i/len(features))
    word2index[feature] = i
  print("End TFIDF")
  return word2index,scores

def print_FLAGS(flags):
  print("***************************************")
  print("do_train: ",flags.do_train)
  print("do_eval: ",flags.do_eval)
  print("do_predict: ",flags.do_predict)
  print("do_recall: ",flags.do_recall)
  print("retrain: ",flags.retrain)
  print("data_dir: ",flags.data_dir)
  print("bert_config_file: ",flags.bert_config_file)
  print("pred_file: ",flags.pred_file)
  print("refer_file: ",flags.refer_file)
  print("task_name: ",flags.task_name)
  print("vocab_file: ",flags.vocab_file)
  print("output_dir: ",flags.output_dir)
  print("init_checkpoint: ",flags.init_checkpoint)
  print("max_seq_length: ",flags.max_seq_length)
  print("train_batch_size: ",flags.train_batch_size)
  print("num_train_epochs: ",flags.num_train_epochs)
  print("save_checkpoints_steps: ",flags.save_checkpoints_steps)
  print("***************************************")

def main(_):
  tf.logging.set_verbosity(tf.logging.INFO)
  print_FLAGS(FLAGS)
  processors = {
      "udc" : UDCProcessor
  }

  tokenization.validate_case_matches_checkpoint(FLAGS.do_lower_case,
                                                FLAGS.init_checkpoint)


  if not FLAGS.do_train and not FLAGS.do_eval and not FLAGS.do_predict and not FLAGS.do_recall:
    raise ValueError(
        "At least one of `do_train`, `do_eval`, `do_predict' or 'do_recall' must be True.")

  bert_config = modeling.BertConfig.from_json_file(FLAGS.bert_config_file)

  if FLAGS.max_seq_length > bert_config.max_position_embeddings:
    raise ValueError(
        "Cannot use sequence length %d because the BERT model "
        "was only trained up to sequence length %d" %
        (FLAGS.max_seq_length, bert_config.max_position_embeddings))

  tf.gfile.MakeDirs(FLAGS.output_dir)

  task_name = FLAGS.task_name.lower()

  if task_name not in processors:
    raise ValueError("Task not found: %s" % (task_name))

  processor = processors[task_name]()

  label_list = processor.get_labels()

  tokenizer = tokenization.FullTokenizer(
      vocab_file=FLAGS.vocab_file, do_lower_case=FLAGS.do_lower_case)

  tpu_cluster_resolver = None
  if FLAGS.use_tpu and FLAGS.tpu_name:
    tpu_cluster_resolver = tf.contrib.cluster_resolver.TPUClusterResolver(
        FLAGS.tpu_name, zone=FLAGS.tpu_zone, project=FLAGS.gcp_project)

  is_per_host = tf.contrib.tpu.InputPipelineConfig.PER_HOST_V2
  run_config = tf.contrib.tpu.RunConfig(
      cluster=tpu_cluster_resolver,
      master=FLAGS.master,
      model_dir=FLAGS.output_dir,
      save_checkpoints_steps=FLAGS.save_checkpoints_steps,
      tpu_config=tf.contrib.tpu.TPUConfig(
          iterations_per_loop=FLAGS.iterations_per_loop,
          num_shards=FLAGS.num_tpu_cores,
          per_host_input_for_training=is_per_host))

  train_examples = None
  num_train_steps = None
  num_warmup_steps = None
  if FLAGS.do_train:
    train_examples = processor.get_train_examples(FLAGS.data_dir)
    num_train_steps = int(
        len(train_examples) / FLAGS.train_batch_size * FLAGS.num_train_epochs)
    num_warmup_steps = int(num_train_steps * FLAGS.warmup_proportion)

  model_fn = model_fn_builder(
      bert_config=bert_config,
      num_labels=len(label_list),
      init_checkpoint=FLAGS.init_checkpoint,
      learning_rate=FLAGS.learning_rate,
      num_train_steps=num_train_steps,
      num_warmup_steps=num_warmup_steps,
      use_tpu=FLAGS.use_tpu,
      use_one_hot_embeddings=FLAGS.use_tpu,
      batch_size=FLAGS.train_batch_size
      )

  # If TPU is not available, this will fall back to normal Estimator on CPU
  # or GPU.
  # estimator = tf.contrib.tpu.TPUEstimator(
  #     use_tpu=FLAGS.use_tpu,
  #     model_fn=model_fn,
  #     config=run_config,
  #     train_batch_size=FLAGS.train_batch_size,
  #     eval_batch_size=FLAGS.eval_batch_size,
  #     predict_batch_size=FLAGS.predict_batch_size)
  estimator = tf.estimator.Estimator(
        model_fn=model_fn,
        model_dir=FLAGS.output_dir,
        config=run_config,
        params={"batch_size":FLAGS.train_batch_size}
  )

  if FLAGS.do_train:
    train_file = os.path.join(FLAGS.output_dir, "train.tf_record")
    
    if(not os.path.exists(FLAGS.output_dir+"/train.tf_record")):
      # print(kkk)
      file_based_convert_examples_to_features(train_examples, label_list, FLAGS.max_seq_length, tokenizer, train_file)
    tf.logging.info("***** Running training *****")
    tf.logging.info("  Num examples = %d", len(train_examples))
    tf.logging.info("  Batch size = %d", FLAGS.train_batch_size)
    tf.logging.info("  Num steps = %d", num_train_steps)
    train_input_fn = file_based_input_fn_builder(
        input_file=train_file,
        seq_length=FLAGS.max_seq_length,
        is_training=True,
        drop_remainder=True)
    estimator.train(input_fn=train_input_fn, max_steps=num_train_steps)

  if FLAGS.do_eval:
    eval_examples = processor.get_dev_examples(FLAGS.data_dir)
    num_actual_eval_examples = len(eval_examples)
    if FLAGS.use_tpu:
      # TPU requires a fixed batch size for all batches, therefore the number
      # of examples must be a multiple of the batch size, or else examples
      # will get dropped. So we pad with fake examples which are ignored
      # later on. These do NOT count towards the metric (all tf.metrics
      # support a per-instance weight, and these get a weight of 0.0).
      while len(eval_examples) % FLAGS.eval_batch_size != 0:
        eval_examples.append(PaddingInputExample())

    eval_file = os.path.join(FLAGS.output_dir, "eval.tf_record")
    file_based_convert_examples_to_features(
        eval_examples, label_list, FLAGS.max_seq_length, tokenizer, eval_file)

    tf.logging.info("***** Running evaluation *****")
    tf.logging.info("  Num examples = %d (%d actual, %d padding)",
                    len(eval_examples), num_actual_eval_examples,
                    len(eval_examples) - num_actual_eval_examples)
    tf.logging.info("  Batch size = %d", FLAGS.eval_batch_size)

    # This tells the estimator to run through the entire set.
    eval_steps = None
    # However, if running eval on the TPU, you will need to specify the
    # number of steps.
    if FLAGS.use_tpu:
      assert len(eval_examples) % FLAGS.eval_batch_size == 0
      eval_steps = int(len(eval_examples) // FLAGS.eval_batch_size)

    eval_drop_remainder = True if FLAGS.use_tpu else False
    eval_input_fn = file_based_input_fn_builder(
        input_file=eval_file,
        seq_length=FLAGS.max_seq_length,
        is_training=False,
        drop_remainder=eval_drop_remainder)

    result = estimator.evaluate(input_fn=eval_input_fn, steps=eval_steps)

    output_eval_file = os.path.join(FLAGS.output_dir, "eval_results.txt")
    with tf.gfile.GFile(output_eval_file, "w") as writer:
      tf.logging.info("***** Eval results *****")
      for key in sorted(result.keys()):
        tf.logging.info("  %s = %s", key, str(result[key]))
        writer.write("%s = %s\n" % (key, str(result[key])))

  if FLAGS.do_predict:
    predict_examples = processor.get_test_examples(FLAGS.data_dir)
    num_actual_predict_examples = len(predict_examples)

    predict_file = os.path.join(FLAGS.output_dir, "predict.tf_record")
    if(not os.path.exists(FLAGS.output_dir+"/predict.tf_record")):
      file_based_convert_examples_to_features(predict_examples, label_list,FLAGS.max_seq_length, tokenizer,predict_file)

    tf.logging.info("***** Running prediction*****")
    tf.logging.info("  Num examples = %d (%d actual, %d padding)",
                    len(predict_examples), num_actual_predict_examples,
                    len(predict_examples) - num_actual_predict_examples)
    tf.logging.info("  Batch size = %d", FLAGS.predict_batch_size)

    predict_drop_remainder = True if FLAGS.use_tpu else False
    predict_input_fn = file_based_input_fn_builder(
        input_file=predict_file,
        seq_length=FLAGS.max_seq_length,
        is_training=False,
        drop_remainder=predict_drop_remainder)
    
    result = estimator.predict(input_fn=predict_input_fn,checkpoint_path=FLAGS.init_checkpoint)

    output_predict_file = os.path.join(FLAGS.output_dir, "test_results.tsv")
    with tf.gfile.GFile(output_predict_file, "w") as writer:
      num_written_lines = 0
      tf.logging.info("***** Predict results *****")
      for (i, prediction) in enumerate(result):
        probabilities = prediction["probabilities"]
        # logic_output = prediction["logic"]
        # similarity_output = prediction["similarity"]
        # np.save("data/output/similarity.npy",similarity_output)
        # np.save("data/output/logic.npy",logic_output)
        if i >= num_actual_predict_examples:
          break
        # final_prob = np.mean(probabilities,axis=0)
        # print(probabilities)
        # print(final_prob)
        # print(kkk)
        
        output_line = "\t".join(
            str(class_probability)
            for class_probability in probabilities) + "\n"
        writer.write(output_line)
        num_written_lines += 1
    assert num_written_lines == num_actual_predict_examples

  if FLAGS.do_recall:
    eval_inst = EvalUDC(FLAGS.pred_file, FLAGS.refer_file)
    eval_metrics = eval_inst.evaluate()
    print("MATCHING TASK: %s metrics in testset: " % task_name)
    print("R1@2: %s" % eval_metrics[0])
    print("R1@10: %s" % eval_metrics[1])
    print("R2@10: %s" % eval_metrics[2])
    print("R5@10: %s" % eval_metrics[3])

if __name__ == "__main__":
  flags.mark_flag_as_required("data_dir")
  flags.mark_flag_as_required("task_name")
  flags.mark_flag_as_required("vocab_file")
  flags.mark_flag_as_required("bert_config_file")
  flags.mark_flag_as_required("output_dir")
  os.environ["CUDA_VISIBLE_DEVICES"] = "1"
  config = tf.ConfigProto()
  config.gpu_options.allow_growth=True
  session = tf.InteractiveSession(config=config)
  tf.app.run()