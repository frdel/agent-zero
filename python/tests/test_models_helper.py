import unittest
from unittest.mock import patch, mock_open
import os

# Adjust import path based on actual location of models.py
# If models.py is in the root, and this test is in python/tests/, the import needs to reflect that.
# Assuming the test runner handles the path correctly or models.py is accessible via PYTHONPATH.
# For now, let's assume direct import is possible or will be adjusted by the runner.
# If models.py is in root: from models import _get_gpt4all_model_path
# If models.py is in python/ (like other helpers): from python.models import _get_gpt4all_model_path

# Based on the project structure, models.py is in the root.
# To make this runnable directly and also by a test runner from root,
# we might need to adjust sys.path or use relative imports if it were a package.
# For now, standard import and expect test runner from root.
from models import _get_gpt4all_model_path


class TestGetGpt4allModelPath(unittest.TestCase):

    @patch('models.dotenv.get_dotenv_value')
    @patch('os.path.isdir')
    @patch('os.path.isfile')
    def test_gpt4all_path_is_file(self, mock_isfile, mock_isdir, mock_get_dotenv_value):
        """
        Test case a: GPT4ALL_MODEL_PATH is a valid file path.
        """
        mock_get_dotenv_value.return_value = "/env/path/to/model.bin"
        mock_isfile.side_effect = lambda path: path == "/env/path/to/model.bin"
        mock_isdir.return_value = False # Not a directory

        expected_path = "/env/path/to/model.bin"
        result_path = _get_gpt4all_model_path("ignored_model_name.bin")
        self.assertEqual(result_path, expected_path)
        mock_get_dotenv_value.assert_called_once_with("GPT4ALL_MODEL_PATH")

    @patch('models.dotenv.get_dotenv_value')
    @patch('os.path.isdir')
    @patch('os.path.isfile')
    def test_gpt4all_path_is_dir(self, mock_isfile, mock_isdir, mock_get_dotenv_value):
        """
        Test case b: GPT4ALL_MODEL_PATH is a valid directory, model_name is a filename.
        """
        env_path = "/env/path/to/models_dir"
        model_filename = "actual_model.bin"
        joined_path = os.path.join(env_path, model_filename)

        mock_get_dotenv_value.return_value = env_path
        mock_isdir.side_effect = lambda path: path == env_path
        mock_isfile.side_effect = lambda path: path == joined_path # Only the joined path is a file

        expected_path = joined_path
        result_path = _get_gpt4all_model_path(model_filename)
        self.assertEqual(result_path, expected_path)
        mock_get_dotenv_value.assert_called_once_with("GPT4ALL_MODEL_PATH")

    @patch('models.dotenv.get_dotenv_value')
    @patch('os.path.isdir')
    @patch('os.path.isfile')
    def test_gpt4all_path_not_set_model_name_is_full_path(self, mock_isfile, mock_isdir, mock_get_dotenv_value):
        """
        Test case c: GPT4ALL_MODEL_PATH not set, model_name is a full valid path.
        """
        model_full_path = "/full/path/to/model.bin"

        mock_get_dotenv_value.return_value = None # GPT4ALL_MODEL_PATH is not set
        mock_isdir.return_value = False
        mock_isfile.side_effect = lambda path: path == model_full_path

        expected_path = model_full_path
        result_path = _get_gpt4all_model_path(model_full_path)
        self.assertEqual(result_path, expected_path)
        mock_get_dotenv_value.assert_called_once_with("GPT4ALL_MODEL_PATH")

    @patch('models.dotenv.get_dotenv_value')
    @patch('os.path.isdir')
    @patch('os.path.isfile')
    def test_gpt4all_path_is_dir_model_not_in_dir_raises_error(self, mock_isfile, mock_isdir, mock_get_dotenv_value):
        """
        Test case d: GPT4ALL_MODEL_PATH is a dir, but joined path is not a file.
        """
        env_path = "/env/path/to/models_dir"
        model_filename = "non_existent_model.bin"

        mock_get_dotenv_value.return_value = env_path
        mock_isdir.side_effect = lambda path: path == env_path
        mock_isfile.return_value = False # No path is a file

        with self.assertRaises(FileNotFoundError) as context:
            _get_gpt4all_model_path(model_filename)

        self.assertIn(f"GPT4All model file not found.", str(context.exception))
        self.assertIn(f"Initial model_name: '{model_filename}'", str(context.exception))
        self.assertIn(f"GPT4ALL_MODEL_PATH (env var): '{env_path}'", str(context.exception))
        self.assertIn(f"Resolved to: '{os.path.join(env_path, model_filename)}'", str(context.exception))


    @patch('models.dotenv.get_dotenv_value')
    @patch('os.path.isdir')
    @patch('os.path.isfile')
    def test_gpt4all_path_not_set_model_name_invalid_path_raises_error(self, mock_isfile, mock_isdir, mock_get_dotenv_value):
        """
        Test case e: GPT4ALL_MODEL_PATH not set, model_name (as full path) is not valid.
        """
        invalid_model_path = "/full/path/to/non_existent_model.bin"

        mock_get_dotenv_value.return_value = None
        mock_isdir.return_value = False
        mock_isfile.return_value = False # No path is a file

        with self.assertRaises(FileNotFoundError) as context:
            _get_gpt4all_model_path(invalid_model_path)

        self.assertIn(f"GPT4All model file not found.", str(context.exception))
        self.assertIn(f"Initial model_name: '{invalid_model_path}'", str(context.exception))
        self.assertIn(f"GPT4ALL_MODEL_PATH (env var): 'None'", str(context.exception))
        self.assertIn(f"Resolved to: '{invalid_model_path}'", str(context.exception))

    @patch('models.dotenv.get_dotenv_value')
    @patch('os.path.isdir')
    @patch('os.path.isfile')
    def test_gpt4all_env_path_not_file_or_dir_model_name_invalid_raises_error(self, mock_isfile, mock_isdir, mock_get_dotenv_value):
        """
        Test case f: GPT4ALL_MODEL_PATH is set but not a file/dir, model_name (as full path) is not valid.
        """
        env_path_invalid = "/env/path/neither_file_nor_dir"
        model_filename = "some_model.bin" # this will be treated as the full path if env_path is invalid

        mock_get_dotenv_value.return_value = env_path_invalid
        # For env_path_invalid:
        mock_isfile.side_effect = lambda path: False # It's not a file, and model_filename is not a file either
        mock_isdir.side_effect = lambda path: False # env_path_invalid is not a dir

        with self.assertRaises(FileNotFoundError) as context:
            _get_gpt4all_model_path(model_filename)

        self.assertIn(f"GPT4All model file not found.", str(context.exception))
        self.assertIn(f"Initial model_name: '{model_filename}'", str(context.exception))
        self.assertIn(f"GPT4ALL_MODEL_PATH (env var): '{env_path_invalid}'", str(context.exception))
        # Because env_path_invalid is neither file nor dir, model_filename becomes the resolved_path
        self.assertIn(f"Resolved to: '{model_filename}'", str(context.exception))


if __name__ == '__main__':
    unittest.main()
