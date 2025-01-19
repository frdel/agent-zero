from git import Repo
from datetime import datetime
import os
from python.helpers import files

def get_git_info():
    # Get the current working directory (assuming the repo is in the same folder as the script)
    repo_path = files.get_base_dir()
    
    # Open the Git repository
    repo = Repo(repo_path)

    # Ensure the repository is not bare
    if repo.bare:
        raise ValueError(f"Repository at {repo_path} is bare and cannot be used.")

    # Get the current branch name
    branch = repo.active_branch.name if repo.head.is_detached is False else ""

    # Get the latest commit hash
    commit_hash = repo.head.commit.hexsha

    # Get the commit date (ISO 8601 format)
    commit_time = datetime.fromtimestamp(repo.head.commit.committed_date).strftime('%y-%m-%d %H:%M')

    # Get the latest tag description (if available)
    short_tag = ""
    try:
        tag = repo.git.describe(tags=True)
        tag_split = tag.split('-')
        if len(tag_split) >= 3:
            short_tag = "-".join(tag_split[:-1])
        else:
            short_tag = tag
    except:
        tag = ""

    version = branch[0].upper() + " " + ( short_tag or commit_hash[:7] )

    # Create the dictionary with collected information
    git_info = {
        "branch": branch,
        "commit_hash": commit_hash,
        "commit_time": commit_time,
        "tag": tag,
        "short_tag": short_tag,
        "version": version
    }

    return git_info