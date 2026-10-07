---
name: viewprinter-social-manager
description: >-
  Use for work through a connected ViewPrinter account and the content around it:
  scheduling or publishing a post to TikTok, Instagram, Facebook, YouTube or X; uploading,
  describing, listing or PERMANENTLY DELETING media held in ViewPrinter; amending or
  cancelling a post that has not gone out; managing account groups and account profiles;
  reading follower and post performance and linking each post to the format that made it;
  and making content before it is posted — developing formats, producing batches and
  presenting them for review in a local workspace. Two capabilities are destructive and
  irreversible: publishing to a real public account, and media_delete, which erases a
  stored file and its bytes. Listing media or posts reads everything in the user's
  ViewPrinter workspaces. Publishing and account tools require ViewPrinter to be connected
  — do NOT use them to schedule anything anywhere else, or for a platform ViewPrinter does
  not support.
metadata:
  version: "2.0.0"
license: MIT
allowed-tools: >-
  ViewPrinter MCP (platforms, accounts, groups, media, posts), and local Python helpers
  that read and write the project's files and a ~/ViewPrinter folder (the review registry,
  the source archive and the user's answers about tools) and call no outside service:
  scripts/learn.py (publication links and posting checkpoints); content-production's
  memory.py and archive.py (project memory, an archive of originals) and tools.py (finds
  local tools by running each one's --version, never a browser); content-review's review scripts, which serve review pages on
  127.0.0.1 only, open them in the user's browser and check them in a headless Chrome with
  its background networking off; and account-profiles' build_review.py
---
