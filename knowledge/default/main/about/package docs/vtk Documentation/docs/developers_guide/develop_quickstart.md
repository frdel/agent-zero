# Quick Start Guide

This is a quick start guide so that you can start contributing to VTK easily.
To understand the process more deeply, you can jump to the [workflow](./git/develop.md#workflow)
section.

## Initial Setup

Before you begin, perform your initial setup using the following steps:

1.  Register [GitLab Access] to create an account and select a user name.

2.  [Fork VTK][] into your user's namespace on GitLab.

3.  Follow the [download instructions](./git/download.md#clone) to create a
    local clone of the main VTK repository:

        $ git clone --recursive https://gitlab.kitware.com/vtk/vtk.git VTK

    The main repository will be configured as your `origin` remote.

4.  Run the [developer setup script][] to prepare your VTK work tree and
    create Git command aliases used below:

        $ ./Utilities/SetupForDevelopment.sh

    This will prompt you for your GitLab username and configure a remote
    called `gitlab` to refer to your fork. It will also setup a data directory for you.
    No need to do anything else.

[GitLab Access]: https://gitlab.kitware.com/users/sign_in
[Fork VTK]: https://gitlab.kitware.com/vtk/vtk/-/forks/new
[developer setup script]: https://gitlab.kitware.com/vtk/vtk/Utilities/SetupForDevelopment.sh

## Development

Create a local branch for your changes:

```
git checkout -b your_branch
```

Make the needed changes in VTK and use git locally to create logically separated commits.
There is no strict requirements regarding git commit messages syntax but a good rule of
thumb to follow is: `General domain: reason for change`, General domain being a class, a module
, a specific system like build or CI.

```
git commit -m "General domain: Short yet informative reason for the change"
```

Build VTK following the [guide][] and fix any build warnings or issues that arise and seems related to your changes.

[guide]: ../build_instructions/build.md
Add/Improve tests in order to ensure your changes are tested. Take a look in the `Testing` directory
of the module you are making changes in to see how the tests are currently built and try to follow the same paradigms.
Run your test locally from your build directory and check that they pass:

```
cmake . && cmake --build .
ctest -VV -R yourTest
```

## Upload

Push your changes to the GitLab fork that you created in the [initial setup](#initial-setup) stage:

```
git push gitlab
```

## Data

If your test uses new data or baselines, you will need to add it to your fork.
For data, add the file names to the list in your module `yourModule/Testing/CMakeLists.txt` and drop the files in `Testing/Data/`.
For baselines, just drop the file in `yourModule/Testing/Data/Baselines` and run the following commands from your build directory:

```
cmake . && cmake --build .
```

This will transform your files into .sha512 files. Check your test is passing by running from your build directory:

```
ctest -VV -R yourTest
```

If it passes, add these .sha512 files and commit them, then push with:

```
git gitlab-push
```

## Create a Merge Request

Once you are happy with the state of your development on your fork, the next step is to create a merge request back into the main VTK repository.

Open [](https://gitlab.kitware.com/username/vtk/-/merge_requests/new) in a browser, select your branch in the list and create a Merge Request against master.

In the description, write an informative explanation of your added features or bugfix. If there is an associated issue, link it with the `#number` in the description.

Tag some VTK maintainers in the description to ensure someone will see it, see here for the complete [list](./git/develop.md#review-a-merge-request).

## Robot Checks

Once the MR is created, our GitLab robot will check multiple things and make automated suggestions. Please read them and try to follow the instructions.
The two standard suggestions are related to formatting errors and adding markdown changelog.

To fix the formatting, just add a comment containing:

```
Do: reformat
```

Then, once the robot has fixed the formatting, fetch the changes locally (this will remove any local changes to your branch)

```
git fetch gitlab
git reset --hard gitlab/your_branch
```

To fix the changelog warning, create, add, commit and push a markdown (.md) file in `Documentation/release/dev` folder.
In this file, write a small markdown paragraph describing the development.
See other .md files in this folder for examples. It may look like this:

```
## Development title

A new feature that does this and that has been introduced.
This specific issue has been fixed in this particular way.
```

Suggestions and best practices on writing the changelog can be found in the `Documentation/release/dev/0-sample-topic.md` file.
This is an optional step but recommended to do for any new feature and user facing issues.

## Reviews

VTK maintainers and developers will review your MR by leaving comments on it. Try to follow their instructions and be patient.
It can take a while to get a MR into mergeable form. This is a mandatory step, and it is absolutely normal to get change requests.

Review comments can be resolved, please resolve a comment once you've taken it into account and pushed related changes
or once you've reached an agreement with the commenter that nothing should be changed.

Once a reviewer is happy with your changes, they will add a `+X` comment. You need at least one `+2` or higher to consider
merging the MR. Two `+1`s do not equal a `+2`. If a reviewer leave a `-1` comment, please discuss with them to understand what is the issue and how it could be fixed.

Once you have pushed new changes, please tag reviewers again so that they can take a look.
If you do not tag reviewers, they may not know to revisit your changes. _Do not hesitate to tag them and ask for help_.

## Continuous Integration

Before merging a MR, the VTK continuous integration (CI) needs to run and be green.
For CI to be functional, please read and follow this [guide](https://discourse.vtk.org/t/the-ultimate-how-to-make-ci-work-with-my-fork-guide/7581).

To run the CI:
 - Click on the Pipelines Tab
 - Click on the last pipeline status badge
 - Press the `Play all manual` arrows on top of the Build and Test stages

Do not hesitate to tag a VTK developer for help if needed.

You then need to wait for CI to run, it can take a while, up to a full day.

A successful CI should be fully green. If that is so, then your MR is ready !

If not, you need to analyse the issues and fix them. Recover the failure information this way:

Click on the pipelines tab, then on the last status badge, then on the `cdash-commit` job.
It will take you to the related CDash report where you will find all information.

Everything in the CDash report should be green except the `NotRun` and `Time` column. Take a look into each issue and fix them locally.
If there are issues in the pipeline but nothing is visible in the CDash, please ask a maintainer for help to figure out if anything should be done.
You can always try to rerun the failed job by clicking on the arrow of the job in the pipeline.

Once you have fixed some issues locally, commit and push them to gitlab, run the CI again and tag reviewers again for follow-up reviews.

## Merging

Once the MR has green CI and you have at least one `+2`, you can ask for a merge. Before that please make sure that:
 - Your commit history is logical (or squashed into a single commit) and cleaned up with good commit messages
 - You are rebased on a fairly recent version of master

If that is not the case, please rebase on master using the following commands:

```
git fetch origin
git rebase -i origin/master
git push gitlab -f
```

The interactive rebase will let you squash commits, reorganize commits and edit commit messages.

After the force push, make sure to run CI again.

Once all is done, tag a VTK developer so that they can perform the merge command.

__Congratulations ! You just contributed to VTK !__
