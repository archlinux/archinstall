# Contributing to archinstall

Any contributons through pull requests are welcome as this project aims to be a community based project to ease some Arch Linux installation steps.<br>
Bare in mind that the future of this repo might be transferred to the official [GitLab repo under Arch Linux](http://gitlab.archlinux.org/archlinux/) *(if they so choose to adopt the project)*.
Therefor guidelines and style changes to the code might come into affect as well as guidelines surrounding bug reporting and discussions.

## Discussions

Currently, questions, bugs and suggestions should be reported through [GitHub issue tracker](https://github.com/Torxed/archinstall/issues).<br>
For less formal discussions there are also a [archinstall Discord server](https://discord.gg/cqXU88y).

## Coding convention

Archinstall's goal is to follow [PEP8](https://www.python.org/dev/peps/pep-0008/) as best as it can with some minor exceptions.<br>
The exceptions to PEP8 are:

 * Archinstall uses [tabs instead of spaces](https://www.python.org/dev/peps/pep-0008/#tabs-or-spaces) simply to make it easier for non-IDE developers to navigate the code *(Tab display-width should be equal to 4 spaces)*. Exception to the rule are comments that need fine-tuned indentation for documentation purposes.
 * [Line length](https://www.python.org/dev/peps/pep-0008/#maximum-line-length) should aim for no more than 100 characters, but not strictly enforced.
 * [Line breaks before/after binary operator](https://www.python.org/dev/peps/pep-0008/#should-a-line-break-before-or-after-a-binary-operator) is not enforced, as long as the style of line breaks are consistent within the same code block.
 * Archinstall should always be saved with **Unix-formatted line endings** and no other platform-specific formats.
 * [Blank lines](https://www.python.org/dev/peps/pep-0008/#blank-lines) before/after imports and functions are not followed and discouraged. One space is commonly used in archinstall.
 * Multiple [Imports](https://www.python.org/dev/peps/pep-0008/#imports) on the same line is allowed, but more than five imports should be avoided on any given line. This simply saves up some space at the top of the file *(for non-IDE developers)* and will not be enforced.
 * [String quotes](https://www.python.org/dev/peps/pep-0008/#string-quotes) follow PEP8, the exception being when creating formatted strings, double-quoted strings are *preferred* but not required on the outer edges *(Example: `f"Welcome {name}"` rather than `f'Welcome {name}'`)*.

Most of these style guidelines have been put into place after the fact *(in an attempt to clean up the code)*.<br>
There might therefor be older code which does not follow the coding convention and the code is subject to change.

## Submitting Changes

Archinstall uses Github's pull-request workflow and all contributions in terms of code should be done through pull requests.<br>

Anyone interested in archinstall may review your code. One of the core developers will merge your pull request when they think it is ready.
For every pull request, we aim to promptly either merge it or say why it is not yet ready; if you go a few days without a reply, please feel free to ping the thread by adding a new comment.

To get your pull request merged sooner, you should explain why you are making the change. For example, you can point to a code sample that is outdated in terms of Arch Linux command lines.
It is also helpful to add links to online documentation or to the implementation of the code you are changing.

Also, do not squash your commits after you have submitted a pull request, as this erases context during review. We will squash commits when the pull request is merged.

At present the core developers are (alphabetically):

 * Anton Hvornum (@Torxed)
 * Jerker Bengtsson (@jaybent)
 * Varun Madiath (@vamega)
 * demostanis (@demostanis)