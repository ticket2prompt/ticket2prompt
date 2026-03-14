# Metadata Database Schema

## Symbols Table

symbol_id
name
type
file_path
repo
start_line
end_line

## Files Table

file_id
file_path
repo
last_modified
commit_count
authors

## Graph Edges Table

from_symbol
to_symbol
relation_type

Possible relation types:

calls
imports
inherits
implements
references

## Git Metadata Table

file_path
last_commit_hash
last_commit_author
commit_frequency
recent_pr