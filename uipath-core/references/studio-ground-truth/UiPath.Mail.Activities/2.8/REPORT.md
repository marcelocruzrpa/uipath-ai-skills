# Ground-truth diff: UiPath.Mail.Activities @ 2.8

- Harvested: `references/studio-ground-truth/UiPath.Mail.Activities/2.8/`
- Profile: `uipath-core\references\version-profiles\UiPath.Mail.Activities\2.8.json`

## Summary
- match: 6
- divergent: 0
- profile_template_missing: 0
- profile_element_not_found: 0
- profile_template_unparseable: 0

## Match

### `ForEachEmailX`
- attrs: `IncludeSubfolders, MailFilter, Mails, NumberOfEmailsLimit, UnreadOnly, WithAttachmentsOnly`

### `GetOutlookMailMessages`
- attrs: `Account, ConnectionMode, Filter, FilterByMessageIds, GetAttachements, MailFolder, MarkAsRead, Messages, OnlyUnreadMessages, OrderByDate, TimeoutMS, Top, UseISConnection`

### `MoveOutlookMessage`
- attrs: `Account, MailFolder, MailMessage`

### `OutlookApplicationCard`
- attrs: `Account, AccountMismatchBehavior`

### `SaveMailAttachments`
- attrs: `Attachments, ExcludeInlineAttachments, FolderPath, Message, OverwriteExisting, ResourceAttachments`

### `SendOutlookMail`
- attrs: `Account, Bcc, Body, Cc, ConnectionMode, ContinueOnError, Importance, IsBodyHtml, IsDraft, MailMessage, ReplyTo, Sensitivity, Subject, TimeoutMS, To, UseISConnection, UseRichTextEditor`
