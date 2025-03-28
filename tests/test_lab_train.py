# SPDX-License-Identifier: Apache-2.0
# pylint: disable=R0801

# Standard
from pathlib import Path
from unittest import mock
from unittest.mock import patch
import json
import os
import platform
import sys
import typing

# Third Party
from click.testing import CliRunner
import pytest

# First Party
from instructlab import lab
from instructlab.configuration import DEFAULTS
from instructlab.train import linux_train

INPUT_DIR = "test_generated"
TRAINING_RESULTS_DIR = "training_results"
CHECKPOINT_DIR_NAME = "checkpoint-1"
MERGED_MODEL_DIR_NAME = "merged_model"
FINAL_RESULTS_DIR_NAME = "final"
CHECKPOINT_DIR = TRAINING_RESULTS_DIR + "/" + CHECKPOINT_DIR_NAME
MERGED_MODEL_DIR = TRAINING_RESULTS_DIR + "/" + MERGED_MODEL_DIR_NAME
FINAL_RESULTS_DIR = TRAINING_RESULTS_DIR + "/" + FINAL_RESULTS_DIR_NAME
LINUX_GGUF_FILE = FINAL_RESULTS_DIR + "/ggml-model-f16.gguf"
MODEL_DIR = "model"
ENCODING = "UTF-8"
TRAINING_FAILURE_MESSAGE = "INTENTIONAL TRAINING FAILURE"


def setup_input_dir(root: typing.Optional[str] = None):
    input_dir = root if root else INPUT_DIR
    run_dir = input_dir + "/2025-01-01_120000"
    os.makedirs(run_dir)
    for f_path in ["train_1.jsonl", "test_1.jsonl"]:
        print(f"Creating {os.path.join(run_dir, f_path)}")
        with open(os.path.join(run_dir, f_path), "w", encoding=ENCODING):
            pass


def setup_linux_dir():
    os.makedirs(CHECKPOINT_DIR)
    for f_path in [
        "added_tokens.json",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer.model",
        "tokenizer_config.json",
    ]:
        with open(os.path.join(CHECKPOINT_DIR, f_path), "w", encoding=ENCODING) as f:
            f.write("{}")
    os.makedirs(MERGED_MODEL_DIR)
    for f_path in ["config.json", "generation_config.json", "1.safetensors"]:
        with open(os.path.join(MERGED_MODEL_DIR, f_path), "w", encoding=ENCODING) as f:
            f.write("{}")


def setup_load(root: typing.Optional[str] = None):
    model_dir = os.path.join(root, MODEL_DIR) if root else MODEL_DIR
    os.makedirs(model_dir)


def is_arm_mac():
    return sys.platform == "darwin" and platform.machine() == "arm64"


def mock_convert_llama_to_gguf(model, pad_vocab):
    with open(LINUX_GGUF_FILE, "w", encoding="utf-8") as fp:
        fp.write(str(model) + str(pad_vocab))
    return LINUX_GGUF_FILE


def run_default_phased_train(cli_runner):
    result = cli_runner.invoke(
        lab.ilab,
        [
            "--config=DEFAULT",
            "model",
            "train",
            "--pipeline",
            "accelerated",
            "--strategy",
            "lab-multiphase",
            "--phased-phase1-data",
            "knowledge_data_path",
            "--phased-phase2-data",
            "skills_data_path",
            "--phased-mt-bench-judge",
            "mt_bench_judge",
            "--phased-phase1-num-epochs",
            "1",
            "--phased-phase2-num-epochs",
            "1",
            "--device",
            "cuda",
            "--skip-user-confirm",
        ],
    )
    return result


def setup_default_phased_training_dirs():
    """
    Write empty object to dummy test files so they're not empty.
    """
    for f_path in [
        "knowledge_data_path",
        "skills_data_path",
    ]:
        with open(f_path, "w", encoding=ENCODING) as f:
            f.write("{}")
    os.makedirs("mt_bench_judge")


@pytest.mark.usefixtures("mock_mlx_package")
class TestLabTrain:
    """Test collection for `ilab model train` command."""

    @patch("instructlab.utils.is_macos_with_m_chip", return_value=True)
    @patch("instructlab.mlx_explore.gguf_convert_to_mlx.load")
    @patch("instructlab.train.lora_mlx.make_data.make_data")
    @patch("instructlab.train.lora_mlx.convert.convert_between_mlx_and_pytorch")
    @patch("instructlab.train.lora_mlx.lora.load_and_train")
    def test_train_mac(
        self,
        load_and_train_mock,
        convert_between_mlx_and_pytorch_mock,
        make_data_mock,
        load_mock,
        is_macos_with_m_chip_mock,
        cli_runner: CliRunner,
    ):
        setup_input_dir()
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "simple",
                "--input-dir",
                INPUT_DIR,
            ],
        )
        assert result.exit_code == 0
        load_mock.assert_not_called()
        load_and_train_mock.assert_called_once()
        assert load_and_train_mock.call_args[1]["model"] is not None
        assert load_and_train_mock.call_args[1]["train"]
        assert load_and_train_mock.call_args[1]["data"] == DEFAULTS.DATASETS_DIR
        assert load_and_train_mock.call_args[1]["adapter_file"] is not None
        assert load_and_train_mock.call_args[1]["iters"] == 100
        assert load_and_train_mock.call_args[1]["save_every"] == 10
        assert load_and_train_mock.call_args[1]["steps_per_eval"] == 10
        assert len(load_and_train_mock.call_args[1]) == 7
        convert_between_mlx_and_pytorch_mock.assert_called_once()
        assert convert_between_mlx_and_pytorch_mock.call_args[1]["hf_path"] is not None
        assert convert_between_mlx_and_pytorch_mock.call_args[1]["mlx_path"] is not None
        assert convert_between_mlx_and_pytorch_mock.call_args[1]["quantize"]
        assert not convert_between_mlx_and_pytorch_mock.call_args[1]["local"]
        assert len(convert_between_mlx_and_pytorch_mock.call_args[1]) == 4
        make_data_mock.assert_called_once()
        assert make_data_mock.call_args[1]["data_dir"] == DEFAULTS.DATASETS_DIR
        assert len(make_data_mock.call_args[1]) == 1
        is_macos_with_m_chip_mock.assert_called_once()

    @patch("instructlab.utils.is_macos_with_m_chip", return_value=True)
    @patch("instructlab.mlx_explore.gguf_convert_to_mlx.load")
    @patch("instructlab.train.lora_mlx.make_data.make_data")
    @patch("instructlab.train.lora_mlx.convert.convert_between_mlx_and_pytorch")
    @patch("instructlab.train.lora_mlx.lora.load_and_train")
    def test_skip_quantize(
        self,
        load_and_train_mock,
        convert_between_mlx_and_pytorch_mock,
        make_data_mock,
        load_mock,
        is_macos_with_m_chip_mock,
        cli_runner: CliRunner,
    ):
        setup_input_dir()
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "simple",
                "--input-dir",
                INPUT_DIR,
                "--skip-quantize",
            ],
        )
        assert result.exit_code == 0
        load_mock.assert_not_called()
        load_and_train_mock.assert_called_once()
        convert_between_mlx_and_pytorch_mock.assert_called_once()
        assert convert_between_mlx_and_pytorch_mock.call_args[1]["quantize"] is False
        make_data_mock.assert_called_once()
        is_macos_with_m_chip_mock.assert_called_once()

    def test_input_error(self, cli_runner: CliRunner):
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "simple",
                "--input-dir",
                "invalid",
            ],
        )
        assert result.exception is not None
        assert "Could not read directory: invalid" in result.output
        assert result.exit_code == 1

    def test_invalid_taxonomy(self, cli_runner: CliRunner):
        os.mkdir(INPUT_DIR)  # Leave out the test and train files
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "simple",
                "--input-dir",
                INPUT_DIR,
            ],
        )
        assert result.exception is not None
        assert (
            f"{INPUT_DIR} does not contain training or test files, did you run `ilab data generate`?"
            in result.output
        )
        assert result.exit_code == 1

    def test_invalid_data_dir(self, cli_runner: CliRunner):
        # The error comes from make_data itself so it's only really useful to test on a mac
        if is_arm_mac():
            os.mkdir(INPUT_DIR)  # Leave out the test and train files
            result = cli_runner.invoke(
                lab.ilab,
                [
                    "--config=DEFAULT",
                    "model",
                    "train",
                    "--pipeline",
                    "simple",
                    "--data-path",
                    "invalid",
                    "--input-dir",
                    INPUT_DIR,
                ],
            )
            assert result.exception is not None
            assert "Could not read from data directory" in result.output
            assert result.exit_code == 1

    @patch("instructlab.utils.is_macos_with_m_chip", return_value=True)
    @patch(
        "instructlab.train.lora_mlx.make_data.make_data",
        side_effect=FileNotFoundError(),
    )
    def test_invalid_data_dir_synthetic(
        self, make_data_mock, is_macos_with_m_chip_mock, cli_runner: CliRunner
    ):
        os.mkdir(INPUT_DIR)  # Leave out the test and train files
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "simple",
                "--data-path",
                "invalid",
                "--input-dir",
                INPUT_DIR,
            ],
        )
        make_data_mock.assert_called_once()
        assert result.exception is not None
        assert "Could not read from data directory" in result.output
        assert result.exit_code == 1
        is_macos_with_m_chip_mock.assert_called_once()

    @patch("instructlab.utils.is_macos_with_m_chip", return_value=True)
    @patch("instructlab.mlx_explore.gguf_convert_to_mlx.load")
    @patch("instructlab.train.lora_mlx.make_data.make_data")
    @patch("instructlab.train.lora_mlx.convert.convert_between_mlx_and_pytorch")
    @patch("instructlab.train.lora_mlx.lora.load_and_train")
    def test_skip_preprocessing(
        self,
        load_and_train_mock,
        convert_between_mlx_and_pytorch_mock,
        make_data_mock,
        load_mock,
        is_macos_with_m_chip_mock,
        cli_runner: CliRunner,
    ):
        setup_input_dir()
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "simple",
                "--input-dir",
                INPUT_DIR,
                "--skip-preprocessing",
            ],
        )
        assert result.exit_code == 0
        load_mock.assert_not_called()
        load_and_train_mock.assert_called_once()
        convert_between_mlx_and_pytorch_mock.assert_called_once()
        make_data_mock.assert_not_called()
        is_macos_with_m_chip_mock.assert_called_once()

    @patch("instructlab.utils.is_macos_with_m_chip", return_value=True)
    @patch("instructlab.mlx_explore.utils.fetch_tokenizer_from_hub")
    @patch("instructlab.mlx_explore.gguf_convert_to_mlx.load")
    @patch("instructlab.train.lora_mlx.make_data.make_data")
    @patch("instructlab.train.lora_mlx.convert.convert_between_mlx_and_pytorch")
    @patch("instructlab.train.lora_mlx.lora.load_and_train")
    def test_load(
        self,
        load_and_train_mock,
        convert_between_mlx_and_pytorch_mock,
        make_data_mock,
        load_mock,
        fetch_tokenizer_from_hub_mock,
        is_macos_with_m_chip_mock,
        cli_runner: CliRunner,
    ):
        setup_input_dir(DEFAULTS.DATASETS_DIR)
        setup_load(DEFAULTS.CHECKPOINTS_DIR)
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "simple",
                "--input-dir",
                DEFAULTS.DATASETS_DIR,
                "--tokenizer-dir",
                "tokenizer",
                "--gguf-model-path",
                "gguf_model",
                "--model-path",
                MODEL_DIR,
            ],
        )
        assert result.exit_code == 0
        load_mock.assert_called_once()
        load_and_train_mock.assert_called_once()
        convert_between_mlx_and_pytorch_mock.assert_not_called()
        make_data_mock.assert_called_once()
        fetch_tokenizer_from_hub_mock.assert_called_once()
        assert fetch_tokenizer_from_hub_mock.call_args[0][0] == "tokenizer"
        assert fetch_tokenizer_from_hub_mock.call_args[0][1] == "tokenizer"
        assert len(fetch_tokenizer_from_hub_mock.call_args[0]) == 2
        is_macos_with_m_chip_mock.assert_called_once()

    @patch("instructlab.utils.is_macos_with_m_chip", return_value=True)
    @patch("instructlab.mlx_explore.utils.fetch_tokenizer_from_hub")
    @patch("instructlab.mlx_explore.gguf_convert_to_mlx.load")
    @patch("instructlab.train.lora_mlx.make_data.make_data")
    @patch("instructlab.train.lora_mlx.convert.convert_between_mlx_and_pytorch")
    @patch("instructlab.train.lora_mlx.lora.load_and_train")
    def test_load_local(
        self,
        load_and_train_mock,
        convert_between_mlx_and_pytorch_mock,
        make_data_mock,
        load_mock,
        fetch_tokenizer_from_hub_mock,
        is_macos_with_m_chip_mock,
        cli_runner: CliRunner,
    ):
        setup_input_dir(DEFAULTS.DATASETS_DIR)
        setup_load(DEFAULTS.CHECKPOINTS_DIR)
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "simple",
                "--input-dir",
                DEFAULTS.DATASETS_DIR,
                "--tokenizer-dir",
                "tokenizer",
                "--gguf-model-path",
                "gguf_model",
                "--model-path",
                MODEL_DIR,
                "--local",
            ],
        )
        print(result.output)
        assert result.exit_code == 0
        load_mock.assert_called_once()
        load_and_train_mock.assert_called_once()
        convert_between_mlx_and_pytorch_mock.assert_not_called()
        make_data_mock.assert_called_once()
        fetch_tokenizer_from_hub_mock.assert_not_called()
        is_macos_with_m_chip_mock.assert_called_once()

    @patch("instructlab.utils.is_macos_with_m_chip", return_value=False)
    @patch.object(linux_train, "linux_train", return_value=Path("training_results"))
    @patch(
        "instructlab.llamacpp.llamacpp_convert_to_gguf.convert_llama_to_gguf",
        side_effect=mock_convert_llama_to_gguf,
    )
    def test_train_linux(
        self,
        convert_llama_to_gguf_mock,
        linux_train_mock,
        is_macos_with_m_chip_mock,
        cli_runner: CliRunner,
    ):
        setup_input_dir()
        setup_linux_dir()
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "simple",
                "--input-dir",
                INPUT_DIR,
            ],
        )
        assert result.exit_code == 0
        convert_llama_to_gguf_mock.assert_called_once()
        assert convert_llama_to_gguf_mock.call_args[1]["model"] == Path(
            "training_results/final"
        )
        assert convert_llama_to_gguf_mock.call_args[1]["pad_vocab"] is True
        assert len(convert_llama_to_gguf_mock.call_args[1]) == 2
        linux_train_mock.assert_called_once()
        print(linux_train_mock.call_args[1])
        assert linux_train_mock.call_args[1]["train_file"] == Path(
            os.path.join(DEFAULTS.DATASETS_DIR, "train_gen.jsonl")
        )
        assert linux_train_mock.call_args[1]["test_file"] == Path(
            os.path.join(DEFAULTS.DATASETS_DIR, "test_gen.jsonl")
        )
        assert linux_train_mock.call_args[1]["num_epochs"] == 10
        assert linux_train_mock.call_args[1]["train_device"] is not None
        assert not linux_train_mock.call_args[1]["four_bit_quant"]
        assert len(linux_train_mock.call_args[1]) == 6
        is_macos_with_m_chip_mock.assert_called_once()
        assert not os.path.isfile(LINUX_GGUF_FILE)

    @patch("instructlab.utils.is_macos_with_m_chip", return_value=False)
    @patch.object(linux_train, "linux_train", return_value=Path("training_results"))
    @patch(
        "instructlab.llamacpp.llamacpp_convert_to_gguf.convert_llama_to_gguf",
        side_effect=mock_convert_llama_to_gguf,
    )
    def test_double_train_linux(
        self,
        convert_llama_to_gguf_mock,
        linux_train_mock,
        is_macos_with_m_chip_mock,
        tmp_path_home,
    ):
        cli_runner = CliRunner()
        with cli_runner.isolated_filesystem(temp_dir=tmp_path_home):
            # re-initialize the defaults
            setup_input_dir(DEFAULTS.DATASETS_DIR)
            setup_input_dir()
            setup_linux_dir()

            # create the files so they already exist
            test_legacy_message = json.dumps(
                {"user": "hi", "system": "hi", "assistant": "hi"}
            )
            test_files_to_create = ["train_gen.jsonl", "test_gen.jsonl"]
            for f in test_files_to_create:
                with open(
                    os.path.join(tmp_path_home, DEFAULTS.DATASETS_DIR, f),
                    "w",
                    encoding=ENCODING,
                ) as outfile:
                    outfile.write(f"{test_legacy_message}\n")

            assert "train_gen.jsonl" in os.listdir(DEFAULTS.DATASETS_DIR)
            assert "test_gen.jsonl" in os.listdir(DEFAULTS.DATASETS_DIR)
            result = cli_runner.invoke(
                lab.ilab,
                [
                    "--config=DEFAULT",
                    "model",
                    "train",
                    "--pipeline",
                    "simple",
                    "--input-dir",
                    DEFAULTS.DATASETS_DIR,
                    "--data-path",
                    DEFAULTS.DATASETS_DIR,
                ],
            )
            assert result.exception is None
            assert result.exit_code == 0
            convert_llama_to_gguf_mock.assert_called_once()
            assert convert_llama_to_gguf_mock.call_args[1]["model"] == Path(
                "training_results/final"
            )
            assert convert_llama_to_gguf_mock.call_args[1]["pad_vocab"] is True
            assert len(convert_llama_to_gguf_mock.call_args[1]) == 2
            linux_train_mock.assert_called_once()
            print(linux_train_mock.call_args[1])
            assert linux_train_mock.call_args[1]["train_file"] == Path(
                os.path.join(DEFAULTS.DATASETS_DIR, "train_gen.jsonl")
            )
            assert linux_train_mock.call_args[1]["test_file"] == Path(
                os.path.join(DEFAULTS.DATASETS_DIR, "test_gen.jsonl")
            )
            assert linux_train_mock.call_args[1]["num_epochs"] == 10
            assert linux_train_mock.call_args[1]["train_device"] is not None
            assert not linux_train_mock.call_args[1]["four_bit_quant"]
            assert len(linux_train_mock.call_args[1]) == 6
            is_macos_with_m_chip_mock.assert_called_once()
            assert not os.path.isfile(LINUX_GGUF_FILE)

            assert "train_gen.jsonl" in os.listdir(DEFAULTS.DATASETS_DIR)
            assert "test_gen.jsonl" in os.listdir(DEFAULTS.DATASETS_DIR)
            # run this test a second time to ensure files are getting selected correctly
            result = cli_runner.invoke(
                lab.ilab,
                [
                    "--config=DEFAULT",
                    "model",
                    "train",
                    "--pipeline",
                    "simple",
                    "--input-dir",
                    DEFAULTS.DATASETS_DIR,
                    "--data-path",
                    DEFAULTS.DATASETS_DIR,
                ],
            )
            # assert result.exit_code == 0
            assert result.exception is None
            assert convert_llama_to_gguf_mock.call_args[1]["model"] == Path(
                "training_results/final"
            )
            assert convert_llama_to_gguf_mock.call_args[1]["pad_vocab"] is True
            assert len(convert_llama_to_gguf_mock.call_args[1]) == 2
            print(linux_train_mock.call_args[1])
            assert linux_train_mock.call_args[1]["train_file"] == Path(
                os.path.join(DEFAULTS.DATASETS_DIR, "train_gen.jsonl")
            )
            assert linux_train_mock.call_args[1]["test_file"] == Path(
                os.path.join(DEFAULTS.DATASETS_DIR, "test_gen.jsonl")
            )
            assert linux_train_mock.call_args[1]["num_epochs"] == 10
            assert linux_train_mock.call_args[1]["train_device"] is not None
            assert not linux_train_mock.call_args[1]["four_bit_quant"]
            assert len(linux_train_mock.call_args[1]) == 6
            assert not os.path.isfile(LINUX_GGUF_FILE)

    @patch("instructlab.utils.is_macos_with_m_chip", return_value=False)
    @patch(
        "instructlab.train.linux_train.linux_train",
        return_value=Path("training_results"),
    )
    @patch(
        "instructlab.llamacpp.llamacpp_convert_to_gguf.convert_llama_to_gguf",
        side_effect=mock_convert_llama_to_gguf,
    )
    def test_num_epochs(
        self,
        convert_llama_to_gguf_mock,
        linux_train_mock,
        is_macos_with_m_chip_mock,
        cli_runner: CliRunner,
    ):
        setup_input_dir()
        setup_linux_dir()
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "simple",
                "--input-dir",
                INPUT_DIR,
                "--num-epochs",
                "2",
            ],
        )
        assert result.exit_code == 0
        convert_llama_to_gguf_mock.assert_called_once()
        linux_train_mock.assert_called_once()
        assert linux_train_mock.call_args[1]["num_epochs"] == 2
        is_macos_with_m_chip_mock.assert_called_once()
        assert not os.path.isfile(LINUX_GGUF_FILE)

        # Test with invalid num_epochs
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--input-dir",
                INPUT_DIR,
                "--num-epochs",
                "two",
            ],
        )
        assert result.exception is not None
        assert result.exit_code == 2
        assert "'two' is not a valid integer" in result.output

    def test_phased_train_failures(
        self,
        cli_runner: CliRunner,
    ):
        setup_default_phased_training_dirs()

        # Run phased training and fail on the first call to train
        run_training_patch = patch(
            "instructlab.training.run_training",
            new=mock.MagicMock(side_effect=Exception(TRAINING_FAILURE_MESSAGE)),
        )
        run_training_patch.start()
        result = run_default_phased_train(cli_runner)
        run_training_patch.stop()
        assert (
            f"Failed during training loop: {TRAINING_FAILURE_MESSAGE}" in result.output
        )
        assert "Training Phase 1/2..." in result.output
        assert result.exit_code == 1

        # Run phased training and let it succeed on the first train and store that in the journal
        run_training_patch = patch(
            "instructlab.training.run_training", new=mock.MagicMock(return_value=None)
        )
        run_training_patch.start()
        result = run_default_phased_train(cli_runner)
        run_training_patch.stop()
        assert (
            "This likely means that no checkpoints were saved from phase 1"
            in result.output
        )
        assert result.exit_code == 1

        # Make sure it picks up on the second phase
        result = run_default_phased_train(cli_runner)
        assert "SKIPPING: Training Phase 1/2; already in Journal" in result.output
        assert "Training Phase 2/2..." in result.output
        # We didn't actually run training so this is expected
        assert (
            "This likely means that no checkpoints were saved from phase 1"
            in result.output
        )
        assert result.exit_code == 1

    def test_invalid_train_request(
        self,
        cli_runner: CliRunner,
    ):
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "accelerated",
                "--strategy",
                "lab-multiphase",
                "--device",
                "cpu",
            ],
        )
        assert (
            "Unable to train with device=cpu and pipeline=accelerated" in result.output
        )
        assert result.exit_code == 1

    @patch("instructlab.training.run_training", return_value=None)
    @patch("instructlab.model.accelerated_train._evaluate_dir_of_checkpoints")
    @patch("instructlab.model.accelerated_train._get_checkpoints", return_value=[])
    def test_skills_only_train(
        self,
        get_checkpoints_mock,
        evaluate_mock,
        run_training_mock,
        cli_runner: CliRunner,
    ):
        setup_default_phased_training_dirs()
        result = cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--pipeline",
                "accelerated",
                "--strategy",
                "lab-skills-only",
                "--phased-phase2-data",
                "skills_data_path",
                "--phased-mt-bench-judge",
                "mt_bench_judge",
                "--phased-phase2-num-epochs",
                "1",
                "--device",
                "cuda",
                "--skip-user-confirm",
            ],
        )
        run_training_mock.assert_called_once()
        evaluate_mock.assert_called_once()
        get_checkpoints_mock.assert_called_once()
        assert result.exit_code == 0

    @patch(
        "instructlab.model.accelerated_train.accelerated_train",
        return_value=0,
    )
    def test_disable_fullstate_saving(
        self, accelerated_train_mock: mock.MagicMock, cli_runner
    ):
        """
        Ensures that when a user attempts to disable full state saving (params, optimizer state, etc.)
        via the --disable-accelerate-full-state-at-epoch flag, the controlling value inside
        the `train_args` object that is passed to `accelerate_training` is correctly disabled.
        """

        setup_default_phased_training_dirs()
        ##################### Default enabled full state saving saving #####################
        cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--strategy",
                "lab-multiphase",
                "--pipeline",
                "accelerated",
                "--device",
                "cuda",
            ],
        )

        passed_train_args = accelerated_train_mock.call_args.kwargs["train_args"]
        assert passed_train_args.accelerate_full_state_at_epoch  # should be True

        ##################### Disabled full state saving #####################
        cli_runner.invoke(
            lab.ilab,
            [
                "--config=DEFAULT",
                "model",
                "train",
                "--strategy",
                "lab-multiphase",
                "--pipeline",
                "accelerated",
                "--device",
                "cuda",
                "--disable-accelerate-full-state-at-epoch",
            ],
        )

        passed_train_args = accelerated_train_mock.call_args.kwargs["train_args"]

        assert not passed_train_args.accelerate_full_state_at_epoch
