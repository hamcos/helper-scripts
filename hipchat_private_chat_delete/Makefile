.PHONY: default docs clean

default: docs

clean:
	rm -f hipchat_private_chat_delete.odt hipchat_private_chat_delete.pdf hipchat_private_chat_delete.docx

docs: hipchat_private_chat_delete.docx hipchat_private_chat_delete.odt hipchat_private_chat_delete.pdf

hipchat_private_chat_delete.docx:

hipchat_private_chat_delete.odt:

hipchat_private_chat_delete.pdf:

hipchat_private_chat_delete.%: README.md
	pandoc --from markdown_github "$<" --output "$@"
