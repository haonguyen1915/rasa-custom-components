import argparse
import asyncio
import os
import sys
import logging
from typing import Text
from rasa.core.domain import Domain
import os
import rasa.utils.io
import rasa.train
from rasa.importers.importer import TrainingDataImporter
from rasa.core.agent import Agent
from rasa.utils.endpoints import ClientResponseError, EndpointConfig
from haolib import *
from rasa.core.policies.ensemble import PolicyEnsemble
from haolib.lib_rasa.evaluation import EvaluateModel
from haolib.lib_cm.arg_parser import ArgParser
logger = logging.getLogger(__name__)


# prj_dir = os.path.join(PR)

def train_nlu(config_file="config.yml", model_directory="models", model_name="current",
              training_data_file="data/nlu.md"):
    from rasa.nlu.training_data import load_data
    from rasa.nlu import config
    from rasa.nlu.model import Trainer

    training_data = load_data(training_data_file)
    trainer = Trainer(config.load(config_file))
    trainer.train(training_data)

    # Attention: trainer.persist stores the model and all meta data into a folder.
    # The folder itself is not zipped.
    model_path = os.path.join(model_directory, model_name)
    model_directory = trainer.persist(model_path, fixed_model_name="nlu")

    logger.info(f"Model trained. Stored in '{model_directory}'.")

    return model_directory


async def train_core(domain_file="domain.yml", model_directory="models", model_name="current",
                     training_data_file="data/stories.md"):
    file_importer = TrainingDataImporter.load_core_importer_from_config(
        "config.yml", domain_file, [training_data_file]
    )
    domain = await file_importer.get_domain()
    config = await file_importer.get_config()
    end_point = EndpointConfig("http://localhost:5055/webhook")
    agent = Agent(
        domain,
        policies=PolicyEnsemble.from_dict(config),
        action_endpoint=end_point
    )
    # training_data_file = "data/tiny_stories.md"
    train_trackers = await agent.load_data(training_data_file)
    agent.train(train_trackers)
    # The folder itself is not zipped.
    model_path = os.path.join(model_directory, model_name, "core")
    agent.persist(model_path)
    # logger.info(f"Model trained. Stored in '{model_path}'.")
    return model_path


async def parse(text: Text, model_path: Text):
    agent = Agent.load(model_path)

    response = await agent.handle_text(text)
    logger.info(f"Text: '{text}'")
    logger.info("Response:")
    logger.info(response)
    print(response)
    return response


async def conversation_loop(model_path: Text):
    end_point = EndpointConfig("http://localhost:5055/webhook")
    agent = Agent.load(model_path, action_endpoint=end_point)
    print("Press 'q' to exit the conversation")
    while True:
        val = input("input: ")
        if val == "q":
            break
        response = await agent.handle_text(val)
        if isinstance(response, list) and len(response) > 0:
            print("Bot: {}".format(response[0]["text"]))


def evaluation_model():
    evaluate_model = EvaluateModel("data/test_data.md", "models/current/nlu")
    evaluate_model.evaluate_all()
    evaluate_model.plot_confussion_matrix_intents()


parser = ArgParser()
parser.add_str("-m", "--mode", choices=["nlu", "core", "eval", "test"], default="test")
args = parser.parse_args()
if __name__ == "__main__":
    logging.basicConfig(filename="log_stream.txt", level=logging.DEBUG)
    loop = asyncio.get_event_loop()
    if args.mode == "nlu":
        train_nlu()
    if args.mode == "core":
        loop.run_until_complete(train_core())
    if args.mode == "eval":
        evaluation_model()
    if args.mode == "test":
        loop.run_until_complete(conversation_loop("models/current"))
