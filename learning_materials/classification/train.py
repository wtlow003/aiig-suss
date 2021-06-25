"""
This script is used to train model and export ML into pickle format for predictions.

Usage:
    python3 train.py
"""

import logging
from pathlib import Path

from pickle import dump

import click
import pandas as pd
import sklearn
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    roc_curve,
    auc,
)
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer

from src.features.preprocessing import make_pipeline, create_sampler, retrieve_columns
from src.utilities.utility import load_data, parse_config, set_logger


def instantiate_model(model, model_config):
    """
    initiate model using eval, implement with defensive programming
    Args:
        ensemble_model [str]: name of the ensemble model

    Returns:
        [sklearn.model]: initiated model
    """
    if model in dir(sklearn.neighbors):
        return eval("sklearn.neighbors." + model)(**model_config)
    else:
        raise NameError(f"{model} is not in sklearn.neighbors")


@click.command()
@click.argument("config_file", type=str, default="src/config.yml")
def train(config_file):
    """Function to train and dump model into pickle format.

    Args:
        config_file ([str]): Path to config file.

    Returns:
        None
    """

    # configure logger
    logger = set_logger("log/train.log")

    # load config from config file
    logger.info(f"Load config from {config_file}.")
    config = parse_config(config_file)

    processed_train = Path(config["train"]["processed_train"])
    model = config["train"]["model"]
    model_config = config["train"]["model_config"]
    model_path = Path(config["train"]["model_path"])
    transformer_path = Path(config["train"]["transformer_path"])
    sampler = config["train"]["sampler"]
    sampler_config = config["train"]["sampler_config"]

    logger.info(f"Config: {config['train']}")

    # loading the dataset
    logger.info(f"-------------------Load the Processed Data-------------------")
    X, y = load_data(processed_train, "Churn Label", type="csv")
    logger.info(f"Cols: {list(X.columns)}")
    logger.info(f"X: {X.shape}")
    logger.info(f"y: {y.shape}")

    # feature engineering for dataset
    num_features, cat_features, _, X = retrieve_columns(X)
    # preprocess = make_pipeline(num_feats, cat_feats)
    preprocess = ColumnTransformer(
        transformers=[
            ("standardscaler", StandardScaler(), num_features),
            ("onehotencoder", OneHotEncoder(), cat_features),
        ],
        remainder="passthrough",
    )
    preprocess_data = preprocess.fit_transform(X)

    # generate sampler for oversampling
    over_sampler = create_sampler(sampler, sampler_config)
    X_samp, y_samp = over_sampler.fit_resample(preprocess_data, y.ravel())
    logger.info(f"Before sampling, count of '1': {sum(y==1)}")
    logger.info(f"After sampling, count of '1': {sum(y_samp==1)}")

    # instantiate model
    logger.info("-------------------Instantiate model-------------------")
    model = instantiate_model(model, model_config)

    # train model
    logger.info(f"Train model using {model}, {model_config}.")
    model.fit(X_samp, y_samp)
    logger.info(f"Train score: {model.score(X_samp, y_samp)}")
    logger.info(
        f"CV score: {cross_val_score(estimator=model, X=X_samp, y=y_samp, cv=5).mean()}"
    )

    # persist transfomer
    logger.info(f"-------------------Persist transformer-------------------")
    transformer_path.parent.mkdir(parents=True, exist_ok=True)
    with open(transformer_path, "wb") as f:
        dump(preprocess, f)

    # persist model
    logger.info(f"-------------------Persist model-------------------")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with open(model_path, "wb") as f:
        dump(model, f)
    logger.info(f"Persisted model to {model_path}")


if __name__ == "__main__":
    train()
