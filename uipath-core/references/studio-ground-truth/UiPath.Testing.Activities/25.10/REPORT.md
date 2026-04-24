# Ground-truth diff: UiPath.Testing.Activities @ 25.10

- Harvested: `references/studio-ground-truth/UiPath.Testing.Activities/25.10/`
- Profile: `uipath-core\references\version-profiles\UiPath.Testing.Activities\25.10.json`

## Summary
- match: 21
- divergent: 0
- profile_template_missing: 0
- profile_element_not_found: 0
- profile_template_unparseable: 0

## Match

### `Address`
- attrs: `AddressResult, City, Country`

### `AttachDocument`
- attrs: `ContinueOnError, FilePath, Tags`

### `BulkAddTestDataQueue`
- attrs: `ContinueOnError, QueueItemsDataTable, QueueName, TimeoutMs`

### `ComparePdfDocuments`
- attrs: `BaselinePath, ComparisonType, ContinueOnFailure, Differences, IgnoreIdenticalItems, IgnoreImagesLocation, IncludeImages, OutputFolderPath, Result, Rules, RulesList, SemanticDifferences, TargetPath`

### `CompareText`
- attrs: `BaselineText, ComparisonType, ContinueOnFailure, Differences, OutputFilePath, Result, Rules, RulesList, SemanticDifferences, TargetText, WordSeparators`

### `CreateComparisonRule`
- attrs: `ComparisonRule, ComparisonRuleType, ContinueOnError, Pattern, RuleName, UsePlaceholder`

### `DeleteTestDataQueueItems`
- attrs: `ContinueOnError, TestDataQueueItems, TimeoutMs`

### `GetTestDataQueueItem`
- attrs: `ContinueOnError, MarkConsumed, Output, QueueName, TimeoutMs`

### `GetTestDataQueueItems`
- attrs: `ContinueOnError, IdFilter, QueueName, Skip, TestDataQueueItemStatus, TestDataQueueItems, TimeoutMs, Top`

### `GivenName`
- attrs: `GivenNameResult`

### `LastName`
- attrs: `LastNameResult`

### `MockActivity`
- attrs: `MockedActivityIdRef`

### `NewAddTestDataQueueItem`
- attrs: `ContinueOnError, QueueName, TimeoutMs`

### `RandomDate`
- attrs: `MaxDate, MinDate, Output`

### `RandomNumber`
- attrs: `Decimals, Max, Min, Output`

### `RandomString`
- attrs: `Case, Length, Output`

### `RandomValue`
- attrs: `FilePath, Value`

### `VerifyControlAttribute`
- attrs: `AlternativeVerificationTitle, ContinueOnFailure, Expression, KeepScreenshots, Operator, OutputArgument, OutputMessageFormat, Result, ScreenshotsPath, TakeScreenshotInCaseOfFailingAssertion, TakeScreenshotInCaseOfSucceedingAssertion`

### `VerifyExpression`
- attrs: `AlternativeVerificationTitle, ContinueOnFailure, Expression, KeepScreenshots, OutputMessageFormat, Result, ScreenshotsPath, TakeScreenshotInCaseOfFailingAssertion, TakeScreenshotInCaseOfSucceedingAssertion`

### `VerifyExpressionWithOperator`
- attrs: `AlternativeVerificationTitle, ContinueOnFailure, FirstExpression, KeepScreenshots, Operator, OutputMessageFormat, Result, ScreenshotsPath, SecondExpression, TakeScreenshotInCaseOfFailingAssertion, TakeScreenshotInCaseOfSucceedingAssertion`

### `VerifyRange`
- attrs: `AlternativeVerificationTitle, ContinueOnFailure, Expression, KeepScreenshots, LowerLimit, OutputMessageFormat, Result, ScreenshotsPath, TakeScreenshotInCaseOfFailingAssertion, TakeScreenshotInCaseOfSucceedingAssertion, UpperLimit, VerificationType`
