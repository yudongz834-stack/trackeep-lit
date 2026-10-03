$ErrorActionPreference = 'Stop'
function Resolve-Collection($Journal, $CollectionKey, $cols) {
    $collKey = ''
    $cm = @($cols | Where-Object { $_.data.name -eq $Journal }); if ($cm.Count -eq 1) { $collKey = $cm[0].key }; if ($CollectionKey) { if (@($cols | Where-Object { $_.key -ceq $CollectionKey }).Count -ne 1) { throw '指定目录不存在或编号不唯一' }; $collKey = $CollectionKey }
    return $collKey
}
$cols = @(
    [pscustomobject]@{key='NATURE01';data=[pscustomobject]@{name='Nature'}},
    [pscustomobject]@{key='TEST0001';data=[pscustomobject]@{name='隔离测试集合'}}
)
$checks = [ordered]@{}
$checks.explicit_different_name = (Resolve-Collection 'Nature' 'TEST0001' $cols) -ceq 'TEST0001'
$checks.explicit_missing_rejected = $false
try { Resolve-Collection 'Nature' 'MISSING1' $cols } catch { $checks.explicit_missing_rejected = $true }
$checks.no_key_unique_name = (Resolve-Collection 'Nature' '' $cols) -ceq 'NATURE01'
$duplicate = $cols + [pscustomobject]@{key='NATURE02';data=[pscustomobject]@{name='Nature'}}
$checks.no_key_ambiguous_no_selection = (Resolve-Collection 'Nature' '' $duplicate) -ceq ''
$checks.explicit_key_case_sensitive = $false
try { Resolve-Collection 'Nature' 'test0001' $cols } catch { $checks.explicit_key_case_sensitive = $true }
$checks.duplicate_key_rejected = $false
try { Resolve-Collection 'Nature' 'TEST0001' ($cols + $cols[1]) } catch { $checks.duplicate_key_rejected = $true }
if (@($checks.Values | Where-Object { -not $_ }).Count) { throw '合成集合验证未通过' }
$checks | ConvertTo-Json
