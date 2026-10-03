param([string]$Engine='D:/dev/trackeep-scripts/zotero-import.ps1')
$ErrorActionPreference='Stop'
$global:MIState=Join-Path $env:TEMP ('metadata-review-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $global:MIState|Out-Null
function Test-Path {param([string]$LiteralPath,[string]$Path) if($LiteralPath -match '[\\/]zotero[.]env$'){return $true};if($LiteralPath){Microsoft.PowerShell.Management\Test-Path -LiteralPath $LiteralPath}else{Microsoft.PowerShell.Management\Test-Path -Path $Path}}
function Get-Content {param([string]$LiteralPath,[string]$Path,[switch]$Raw,[string]$Encoding)
 if($LiteralPath -match '[\\/]zotero[.]env$'){return @('ZOTERO_USER_ID=0','ZOTERO_API_KEY=synthetic-offline')}
 if($LiteralPath -eq 'SYNTHETIC_EXPECTED'){return ConvertTo-Json -InputObject @($global:MIPins) -Depth 10}
 throw 'TEST GUARD: unexpected file read'
}
function Start-Sleep {}
function Invoke-WebRequest {param([string]$Uri,[string]$Method='GET',$Headers,$Body,$ContentType,[switch]$UseBasicParsing,[int]$TimeoutSec)
 $global:MICalls.Add([pscustomobject]@{uri=$Uri;method=$Method})
 if($Method -eq 'Post'){
  if($Uri -ne 'https://api.zotero.org/users/0/items'){throw 'TEST GUARD: wrong write endpoint'}
  $global:MIPosted=ConvertFrom-Json ([Text.Encoding]::UTF8.GetString($Body))
  $r=@{successful=@{};failed=@{}}
  for($n=0;$n -lt $global:MIPosted.Count;$n++){
   $key=if($global:MIMode -eq 'duplicate_key'){'NEW00001'}else{'NEW0000'+($n+1)}
   $data=$global:MIPosted[$n]
   if($global:MIMode -eq 'wrong_response_identity'){$data.extra='PMID: 999';$data.title='WRONG'}
   if($global:MIMode -eq 'partial' -and $n -eq 1){$r.failed["$n"]=@{code=400;message='synthetic failure'}}else{$r.successful["$n"]=@{key=$key;data=$data}}
  }
  if($global:MIMode -eq 'missing_response'){$r.successful=@{}}
  $text=ConvertTo-Json $r -Depth 12
 }elseif($Method -ne 'GET'){throw 'TEST GUARD: destructive request'}
 elseif($Uri -like '*efetch.fcgi*'){
  $text='<PubmedArticleSet>'
  foreach($a in $global:MIFetched){$text+="<PubmedArticle><MedlineCitation><PMID>$($a.pmid)</PMID><Article><ArticleTitle>$($a.title)</ArticleTitle><Journal><Title>Science</Title><ISOAbbreviation>Science</ISOAbbreviation></Journal></Article><MedlineJournalInfo><NlmUniqueID>$($a.nlm_id)</NlmUniqueID></MedlineJournalInfo></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType='doi'>$($a.doi)</ArticleId></ArticleIdList></PubmedData></PubmedArticle>"};$text+='</PubmedArticleSet>'
 }elseif($Uri -like 'https://api.zotero.org/users/0/collections?*'){$text=ConvertTo-Json -InputObject @($global:MICols) -Depth 10}
 elseif($Uri -like 'https://api.zotero.org/users/0/items?*'){$text=ConvertTo-Json -InputObject @($global:MILive) -Depth 10}
 else{throw 'TEST GUARD: unknown endpoint'}
 return [pscustomobject]@{RawContentStream=[IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes($text))}
}
$results=@()
foreach($mode in @('single','multi','multi_reordered','unicode','missing_fetch','duplicate_fetch','wrong_pmid','wrong_doi','wrong_title','wrong_nlm','wrong_collection','existing','trashed','conflict','normalized_doi','same_title','wrong_response_identity','duplicate_key','missing_response','partial')){
 $global:MIMode=$mode;$global:MICalls=[Collections.Generic.List[object]]::new();$global:MIPosted=@()
 $global:MIPins=@(@{pmid='101';doi='10.1/a';title='Title A';nlm_id='0404511'})
 if($mode -in @('multi','multi_reordered','duplicate_key','partial','missing_fetch','duplicate_fetch')){$global:MIPins+=@{pmid='102';doi='10.1/b';title='Title B';nlm_id='0404511'}}
 $global:MIFetched=@($global:MIPins|ForEach-Object {$_.Clone()});$global:MILive=@();$global:MICols=@(@{key='COLL0001';data=@{name='Science'}})
 switch($mode){
 'multi_reordered'{$global:MIFetched=@($global:MIFetched[1],$global:MIFetched[0])}
 'unicode'{$global:MIPins[0].title='研究 α & β';$global:MIFetched[0].title='研究 <i>α</i> &amp; β'}
 'missing_fetch'{$global:MIFetched=@($global:MIFetched[0])}
 'duplicate_fetch'{$global:MIFetched=@($global:MIFetched[0],$global:MIFetched[0])}
 'wrong_pmid'{$global:MIFetched[0].pmid='999'}
 'wrong_doi'{$global:MIFetched[0].doi='10.1/wrong'}
 'wrong_title'{$global:MIFetched[0].title='Wrong title'}
 'wrong_nlm'{$global:MIFetched[0].nlm_id='wrong'}
 'wrong_collection'{$global:MICols[0].data.name='Nature'}
 'existing'{$global:MILive=@(@{key='OLD00001';data=@{DOI='10.1/a';extra='PMID: 101';title='Title A';itemType='journalArticle'}})}
 'trashed'{$global:MILive=@(@{key='OLD00001';data=@{DOI='10.1/a';extra='PMID: 101';title='Title A';deleted=1}})}
 'conflict'{$global:MILive=@(@{key='OLD00001';data=@{DOI='10.1/a';extra='PMID: 999';title='Other'}})}
 'normalized_doi'{$global:MILive=@(@{key='OLD00001';data=@{DOI='HTTPS://DOI.ORG/10.1/A';extra='';title='Title A'}})}
 'same_title'{$global:MILive=@(@{key='OLD00001';data=@{DOI='10.1/other';extra='PMID: 999';title='Title A'}})}
 }
 $errorText='';$out='';$state=Join-Path $global:MIState $mode
 try{$out=& $Engine -Journal Science -ArticlePmids ($global:MIPins.pmid -join ',') -CollectionKey COLL0001 -ExpectedRecordsPath SYNTHETIC_EXPECTED -StateDir $state -EmitJson -Execute 6>&1|Out-String}catch{$errorText=$_.Exception.Message}
 $line=@($out -split "`n"|Where-Object {$_ -like 'TRACKEEP_JSON *'})|Select-Object -Last 1
 $receipt=if($line){$line.Substring(14)|ConvertFrom-Json}else{$null}
 $results+=@{case=$mode;error=$errorText;post_count=@($global:MICalls|Where-Object method -eq Post).Count;receipt=$receipt}
}
[ordered]@{schema='metadata-engine-independent@1';engine=$Engine;engine_sha256=(Get-FileHash -LiteralPath $Engine -Algorithm SHA256).Hash;network='all Invoke-WebRequest mocked';secret='synthetic in-memory only';state=$global:MIState;results=$results}|ConvertTo-Json -Depth 15|Set-Content -Encoding utf8 D:/trackeep-lit/日志/metadata-validation/independent-engine-results.json
$results|ForEach-Object {[pscustomobject]@{case=$_.case;posts=$_.post_count;error=$_.error;imported=$_.receipt.counts.imported}}|ConvertTo-Json -Compress
