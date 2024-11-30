Develop
=======

This page documents how to develop VTK using [GitLab][] and [Git][].
See the [README](README.md) for more information.

[GitLab]: https://gitlab.kitware.com
[Git]: https://git-scm.com

Git is an extremely powerful version control tool that supports many
different "workflows" for individual development and collaboration.
Here we document procedures used by the VTK development community.
In the interest of simplicity and brevity we do *not* provide an
explanation of why we use this approach.

For a quickstart guide see [here](../develop_quickstart.md)

Workflow
--------

VTK development uses a [branchy workflow][] based on topic branches.
Our collaboration workflow consists of three main steps:

1.  Local Development:
    * [Update](#update)
    * [Create a Topic](#create-a-topic)

2.  Code Review (requires [GitLab Access][]):
    * [Share a Topic](#share-a-topic)
    * [Create a Merge Request](#create-a-merge-request)
    * [Review a Merge Request](#review-a-merge-request)
    * [Revise a Topic](#revise-a-topic)

3.  Integrate Changes:
    * [Merge a Topic](#merge-a-topic) (requires permission in GitLab)
    * [Delete a Topic](#delete-a-topic)

[GitLab Access]: https://gitlab.kitware.com/users/sign_in
[branchy workflow]: https://public.kitware.com/Wiki/Git/Workflow/Topic

Update
------

1.  Update your local `master` branch:

        $ git checkout master
        $ git pull

2.  Optionally push `master` to your fork in GitLab:

        $ git push gitlab master
    to keep it in sync.  The `git gitlab-push` script used to
    [Share a Topic](#share-a-topic) below will also do this.

Create a Topic
--------------

All new work must be committed on topic branches.
Name topics like you might name functions: concise but precise.
A reader should have a general idea of the feature or fix to be developed given just the branch name.

1.  To start a new topic branch:

        $ git fetch origin

2.  For new development, start the topic from `origin/master`:

        $ git checkout -b my-topic origin/master

    For release branch fixes, start the topic from `origin/release`, and
    by convention use a topic name starting in `release-`:

        $ git checkout -b release-my-topic origin/release

    If backporting a change, you may rebase the branch back onto
    `origin/release`:

        $ git checkout -b release-my-topic my-topic
        $ git rebase --onto origin/release origin/master

    Alternatively, for more targeted or aggregate backports, use the `-x` flag
    when performing `git cherry-pick` so that a reference to the original
    commit is added to the commit message:

        $ git checkout -b release-my-topic origin/release
        $ git cherry-pick -x $hash_a $hash_b $hash_c
        $ git cherry-pick -x $hash_d $hash_e $hash_f

3.  Edit files and create commits (repeat as needed):

        $ edit file1 file2 file3
        $ git add file1 file2 file3
        $ git commit

    Caveats:
    * To add data follow [these instructions](test.md#add-data).
    * If your change modifies third party code, see [Updating Third Party Projects](thirdparty.md).
    * To deprecate APIs, see [Deprecation Process](deprecation.md).

Guidelines for Commit logs
--------------------------

Remember to *motivate & summarize*. When writing commit logs, make sure
that there is enough information there for any developer to read and glean
relevant information such as:

1.  Is this change important and why?
2.  If addressing an issue, which issue(s)?
3.  If a new feature, why is it useful and/or necessary?
4.  Are there background references or documentation?

A short description of what the issue being addressed and how will go a long way
towards making the log more readable and the software more maintainable.

Style guidelines for commit logs are as follows:

1. Separate subject from body with a blank line
2. Limit the subject line to 60 characters
3. Capitalize the subject line
4. Use the imperative mood in the subject line e.g. "Refactor foo" or "Fix Issue #12322",
   instead of "Refactoring foo", or "Fixing issue #12322".
5. Wrap the body at 80 characters
6. Use the body to explain `what` and `why` and if applicable a brief `how`.

Share a Topic
-------------

When a topic is ready for review and possible inclusion, share it by pushing
to a fork of your repository in GitLab.  Be sure you have registered and
signed in for [GitLab Access][] and created your fork by visiting the main
[VTK GitLab][] repository page and using the "Fork" button in the upper right.

[VTK GitLab]: https://gitlab.kitware.com/vtk/vtk

1.  Checkout the topic if it is not your current branch:

        $ git checkout my-topic

2.  Check what commits will be pushed to your fork in GitLab:

        $ git prepush

3.  Push commits in your topic branch to your fork in GitLab:

        $ git gitlab-push

    Notes:
    * If you are revising a previously pushed topic and have rewritten the
      topic history, add `-f` or `--force` to overwrite the destination.
    * If the topic adds data see [this note](test.md#push).
    * The `gitlab-push` script also pushes the `master` branch to your
      fork in GitLab to keep it in sync with the upstream `master`.

    The output will include a link to the topic branch in your fork in GitLab
    and a link to a page for creating a Merge Request.

Create a Merge Request
----------------------

(If you already created a merge request for a given topic and have reached
this step after revising it, skip to the [next step](#review-a-merge-request).)

Visit your fork in GitLab, browse to the "**Merge Requests**" link on the
left, and use the "**New Merge Request**" button in the upper right to
reach the URL printed at the end of the [previous step](#share-a-topic).
It should be of the form:

    https://gitlab.kitware.com/<username>/vtk/-/merge_requests/new

Follow these steps:

1.  In the "**Source branch**" box select the `<username>/vtk` repository
    and the `my-topic` branch.

2.  In the "**Target branch**" box select the `vtk/vtk` repository and
    the `master` branch.  It should be the default.

    If your change is a fix for the `release` branch, you should still
    select the `master` branch as the target because the change needs
    to end up there too.

    For other `release` branches (e.g., `release-6.3`), merge requests should
    go directly to the branch (they are not tied with `master` in our
    workflow).

3.  Use the "**Compare branches**" button to proceed to the next page
    and fill out the merge request creation form.

4.  In the "**Title**" field provide a one-line summary of the entire
    topic.  This will become the title of the Merge Request.

    Example Merge Request Title:

        Wrapping: Add Java 1.x support

5.  In the "**Description**" field provide a high-level description
    of the change the topic makes and any relevant information about
    how to try it.
    *   Use `@username` syntax to draw attention of specific developers.
        This syntax may be used anywhere outside literal text and code
        blocks.  Or, wait until the [next step](#review-a-merge-request)
        and add comments to draw attention of developers.
    *   If your change is a fix for the `release` branch, indicate this
        so that a maintainer knows it should be merged to `release`.
    *   Optionally use a fenced code block with type `message` to specify
        text to be included in the generated merge commit message when the
        topic is [merged](#merge-a-topic).

    Example Merge Request Description:

        This branch requires Java 1.x which is not generally available yet.
        Get Java 1.x from ... in order to try these changes.

        ```message
        Add support for Java 1.x to the wrapping infrastructure.
        ```

        Cc: @user1 @user2

6.  The "**Assign to**", "**Milestone**", and "**Labels**" fields
    may be left blank.

7.  Use the "**Submit merge request**" button to create the merge request
    and visit its page.

Guidelines for Merge Requests
-----------------------------

Remember to *motivate & summarize*. When creating a merge request, consider the
reviewers and future perusers of the software. Provide enough information to motivate
the merge request such as:

1.  Is this merge request important and why?
2.  If addressing an issue, which issue(s)?
3.  If a new feature, why is it useful and/or necessary?
4.  Are there background references or documentation?

Also provide a summary statement expressing what you did and if there is a choice
in implementation or design pattern, the rationale for choosing a certain path.
Notable software or data features should be mentioned as well.

A well written merge request will motivate your reviewers, and bring them up
to speed faster. Future software developers will be able to understand the
reasons why something was done, and possibly avoid chasing down dead ends,
Although it may take you a little more time to write a good merge request,
you'll likely see payback in faster reviews and better understood and
maintainable software.

Review a Merge Request
----------------------

Add comments mentioning specific developers using `@username` syntax to
draw their attention and have the topic reviewed.  After typing `@` and
some text, GitLab will offer completions for developers whose real names
or user names match.

Here is a list of developers usernames and their specific area of
expertise. A merge request without a developer tagged has very low chance
to be merged in a reasonable timeframe.

 * @mwestphal: Qt, filters, data Model, widgets, parallel, anything else.
 * @charles.gueunet: filters, data model, SMP, events, pipeline, computational geometry, distributed algorithms.
 * @kmorel: General VTK Expertise, VTK-m accelerators.
 * @demarle: Ray tracing.
 * @will.schroeder: algorithms, computational geometry, filters, SPH, SMP, widgets,  point cloud, spatial locators.
 * @sujin.philip: VTK-m Accelerators, SMP, DIY.
 * @yohann.bearzi: filters, data model, HTG, computational geometry, algorithms.
 * @sebastien.jourdain: web, WebAssembly, Python, Java.
 * @allisonvacanti: VTK-m, vtkDataArray, vtkArrayDispatch, vtk::Range, data model, text rendering.
 * @sankhesh: volume rendering, Qt, OpenGL, widgets, vtkImageData, DICOM, VR.
 * @ben.boeckel: CMake, module system, third-parties.
 * @cory.quammen: readers, filters, data modeling, general usage, documentation.
 * @seanm: macOS, Cocoa, cppcheck, clang.
 * @spiros.tsalikis: filters, SMP, computational geometry.
 * @thomas.galland: readers, filters, selection, VR.

If you would like to be included in this list, juste create a merge request.

### Human Reviews ###

Reviewers may add comments providing feedback or to acknowledge their
approval. When a human reviewers suggest a change, please take it into
account or discuss your choices with the reviewers until an agreement
is reached. At this point, please `resolve` the discussion by clicking
on the dedicated button.

When all discussion have been addressed, the reviewers will either do
another pass of comment or acknowledge their approval in some form.

Please be swift to address or discuss comments, it will increase
the speed at which your changes will be merged.

### Comments Formatting ###

Comments use [GitLab Flavored Markdown][] for formatting.  See GitLab
documentation on [Special GitLab References][] to add links to things
like merge requests and commits in other repositories.

[GitLab Flavored Markdown]: https://gitlab.kitware.com/help/markdown/markdown
[Special GitLab References]: https://gitlab.kitware.com/help/markdown/markdown#special-gitlab-references

Lines of specific forms will be extracted during
[merging](#merge-a-topic) and included as trailing lines of the
generated merge commit message.

A commit message consists of up to three parts which must be specified
in the following order: the [leading line](#leading-line), then
[middle lines](#middle-lines), then [trailing lines](#trailing-lines).
Each part is optional, but they must be specified in this order.

#### Leading Line ####

The *leading* line of a comment may optionally be exactly one of the
following votes followed by nothing but whitespace before the end
of the line:

* `-1` or `:-1:` indicates "the change is not ready for integration".
* `+1` or `:+1:` indicates "I like the change".
  This adds an `Acked-by:` trailer to the merge commit message.
* `+2` indicates "the change is ready for integration".
  This adds a `Reviewed-by:` trailer to the merge commit message.
* `+3` indicates "I have tested the change and verified it works".
  This adds a `Tested-by:` trailer to the merge commit message.

#### Middle Lines ####

The middle lines of a comment may be free-form [GitLab Flavored Markdown][].

#### Trailing Lines ####

Zero or more *trailing* lines in the last section of a comment may
each contain exactly one of the following votes followed by nothing
but whitespace before the end of the line:

*   `Rejected-by: me` means "The change is not ready for integration."
*   `Acked-by: me` means "I like the change but defer to others."
*   `Reviewed-by: me` means "The change is ready for integration."
*   `Tested-by: me` means "I have tested the change and verified it works."

Each `me` reference may instead be an `@username` reference or a full
`Real Name <user@domain>` reference to credit someone else for performing
the review.  References to `me` and `@username` will automatically be
transformed into a real name and email address according to the user's
GitLab account profile.

#### Fetching Changes ####

One may fetch the changes associated with a merge request by using
the `git fetch` command line shown at the top of the Merge Request
page.  It is of the form:

    $ git fetch https://gitlab.kitware.com/$username/vtk.git $branch

This updates the local `FETCH_HEAD` to refer to the branch.

There are a few options for checking out the changes in a work tree:

*   One may checkout the branch:

        $ git checkout FETCH_HEAD -b $branch
    or checkout the commit without creating a local branch:

        $ git checkout FETCH_HEAD

*   Or, one may cherry-pick the commits to minimize rebuild time:

        $ git cherry-pick ..FETCH_HEAD

### Robot Reviews ###

The "Kitware Robot" automatically performs basic checks on the commits
and adds a comment acknowledging or rejecting the topic.  This will be
repeated automatically whenever the topic is pushed to your fork again.
A re-check may be explicitly requested by adding a comment with a single
[*trailing* line](#trailing-lines):

    Do: check

A topic cannot be [merged](#merge-a-topic) until the automatic review
succeeds.

### Continuous Integration ###

VTK uses [GitLab CI](https://gitlab.kitware.com/help/ci/examples/README.md) to
test its functionality. CI results are published to CDash and a link is added
to the `External` stage of the CI pipeline by `@kwrobot`. Developers and
reviewers should start jobs which make sense for the change using the following
methods:

- The first thing to check is that CI is enabled in your fork of VTK.

 1. Navigate to your fork (change the username in the URL): (https://gitlab.kitware.com/username/vtk/)
 2. Click on `Settings > General`, then expand "Visibility, project features, permissions"
 3. Make sure `Project Visbility` is `Public` and `CI/CD` is enabled for `Everyone With Access`
 4. Click on `Settings > CI/CD`, then expand `General`
 5. Make sure `Public Pipelines` is enabled

- The simplest way to trigger CI on a merge request is by adding a comment
  with a command among the [trailing lines](#trailing-lines):

    Do: test

  `@kwrobot` will add an award emoji to the comment to indicate that it was
  processed and trigger all jobs that are awaiting manual interaction in the
  merge request's pipelines.

  The `Do: test` command accepts the following arguments:

  * `--named <regex>` or `-n <regex>`: Trigger jobs matching `<regex>` anywhere
    in their name. Job names may be seen on the merge request's Pipelines tab.
  * `--stage <stage>` or `-s <stage>`: Only affect jobs in a given stage. Stage
    names may be seen on the merge request's Pipelines tab. Note that the stage
    names are determined by what is in the `.gitlab-ci.yml` file and may be
    capitalized in the web page, so lowercasing the webpage's display name for
    stages may be required.
  * `--action <action>` or `-a <action>`: The action to perform on the jobs.
    Possible actions:

    - `manual` (the default): Start jobs awaiting manual interaction.
    - `unsuccessful`: Start or restart jobs which have not completed
      successfully.
    - `failed`: Restart jobs which have completed, but without success.
    - `completed`: Restart all completed jobs.
  * There is a `quick` stage, so unless you are confident the CI will pass, it is preferable
    to run only that by doing:

      Do: test -s quick

  * It is even possible to start a single job be navigating in the merge request's pipeline and
    click on individual play button. This is a great way to test quickly run a smoke test or
    debug CI issues without wasting CI resources.

If the merge request topic branch is updated by a push, a new manual trigger
using one of the above methods is needed to start CI again.

Before the merge, all the jobs, including tidy, must be run and reviewed, see below.

If you have any question about the CI process, do not hesitate to ask a CI maintainer:
 - @ben.boeckel
 - @mwestphal

### Reading CI Results ###

Reading CI results is a very important part of the merge request process
and is the responsibility of the author of the merge request, although reviewers
can usually help. There are two locations to read the results, GitLab CI and CDash.
Both should be checked and considered clean before merging.

To read GitLab CI result, click on the Pipelines tab then on the last pipeline.
It is expected to be fully green. If there is a yellow warning job, please consult CDash.
If there is a red failed job, click on it to see the reason for the failure.
It should clearly appears at the bottom of the log.
Possible failures are:
 - Timeouts: please rerun the job and report to CI maintainers
 - Memory related errors: please rerun the job and report to CI maintainers
 - Testing errors: please consult CDash for more information, usually an issue in your code
 - Non disclosed error: please consult CDash, usually a build error in your code

To read CDash results, on the job page, click on the "cdash-commit" external job which
will open the commit-specific CDash page. Once it is open, make sure to show "All Build" on the bottom left of the page.
CDash results displays error, warnings, and test failures for all the jobs.
It is expected to be green *except* for the "NoRun" and "Test Timings" categories, which can be ignored.

 - Configure warnings: there **must** not be any; to fix before the merge
 - Configure errors: there **must** not be any; to fix before the merge
 - Build warnings: there **must** not be any; to fix before the merge. If unrelated to your code, report to CI maintainers.
 - Build errors: there **must** not be any; to fix before the merge. If unrelated to your code, rerun the job and report to CI maintainers.
 - NotRun test : ignore; these tests have self-diagnosed that they are not relevant on the testing machine.
 - Testing failure: there **should** not be any, ideally, to fix before the merge. If unrelated to your code, check the test history to see if it is a flaky test and report to CI maintainers.
 - Testing success: if your MR creates or modifies tests, please check that your test are listed there.
 - Test timings errors: can be ignored, but if it is all red, you may want to report it to CI maintainers.

To check the history of a failing test, on the test page, click on the "Summary" link to see a summary of the test for the day,
then click on the date controls on the top of the page to go back in time.
If the test fails on other MRs or on master, this is probably a flaky test, currently in the process of being fixed or excluded.
A flaky test can be ignored.

As a reminder, here is our current policy regarding CI results.
All the jobs must be run before merging, *including tidy*.
Configure warnings and errors are not acceptable to merge and must be fixed.
Build warning and errors are not acceptable to merge and must be fixed.
Testing failure should be fixed before merging but can be accepted if a flaky test has been clearly identified.

Revise a Topic
--------------

If a topic is approved during GitLab review, skip to the
[next step](#merge-a-topic).  Otherwise, revise the topic
and push it back to GitLab for another review as follows:

1.  Checkout the topic if it is not your current branch:

        $ git checkout my-topic

2.  To revise the `3`rd commit back on the topic:

        $ git rebase -i HEAD~3

    (Substitute the correct number of commits back, as low as `1`.)
    Follow Git's interactive instructions.

3.  Return to the [above step](#share-a-topic) to share the revised topic.

Merge a Topic
-------------

Once review has concluded that the MR topic is ready for integration
(at least one `+2`), authorized developers may add a comment with a single
[*trailing* line](#trailing-lines):

    Do: merge

in order for your change to be merged into the upstream repository.

If your merge request has been already approved by developers
but not merged yet, do not hesitate to tag an authorized developer
and ask for a merge.

By convention, do not request a merge if any `-1` or `Rejected-by:`
review comments have not been resolved and superseded by at least
`+1` or `Acked-by:` review comments from the same user.

The `Do: merge` command accepts the following arguments:

* `-t <topic>`: substitute `<topic>` for the name of the MR topic
  branch in the constructed merge commit message.

Additionally, `Do: merge` extracts configuration from trailing lines
in the MR description (the following have no effect if used in a MR
comment instead):

* `Backport: release[:<commit-ish>]`: merge the topic branch into
  the `release` branch to backport the change.  This is allowed
  only if the topic branch is based on a commit in `release` already.
  If only part of the topic branch should be backported, specify it as
  `:<commit-ish>`.  The `<commit-ish>` may use [git rev-parse](https://git-scm.com/docs/git-rev-parse)
  syntax to reference commits relative to the topic `HEAD`.
  See additional [backport instructions](https://gitlab.kitware.com/utils/git-workflow/-/wikis/Backport-topics) for details.
  For example:

 * `Backport: release`
    Merge the topic branch head into both `release` and `master`.
 * `Backport: release:HEAD~1^2`
    Merge the topic branch head's parent's second parent commit into
    the `release` branch.  Merge the topic branch head to `master`.

* `Topic-rename: <topic>`: substitute `<topic>` for the name of
  the MR topic branch in the constructed merge commit message.
  It is also used in merge commits constructed by `Do: stage`.
  The `-t` option to a `Do: merge` command overrides any topic
  rename set in the MR description.

### Merge Success ###

If the merge succeeds the topic will appear in the upstream repository
`master` branch and the Merge Request will be closed automatically.

### Merge Failure ###

If the merge fails (likely due to a conflict), a comment will be added
describing the failure.  In the case of a conflict, fetch the latest
upstream history and rebase on it:

    $ git fetch origin
    $ git rebase origin/master

(If you are fixing a bug in the latest release then substitute
`origin/release` for `origin/master`.)

Return to the [above step](#share-a-topic) to share the revised topic.

Delete a Topic
--------------

After a topic has been merged upstream the Merge Request will be closed.
Now you may delete your copies of the branch.

1.  In the GitLab Merge Request page a "**Remove Source Branch**"
    button will appear.  Use it to delete the `my-topic` branch
    from your fork in GitLab.

2.  In your work tree checkout and update the `master` branch:

        $ git checkout master
        $ git pull

3.  Delete the local topic branch:

        $ git branch -d my-topic

    The `branch -d` command works only when the topic branch has been
    correctly merged.  Use `-D` instead of `-d` to force the deletion
    of an unmerged topic branch (warning - you could lose commits).
