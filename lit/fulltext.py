"""PDF 身份校验与 Zotero 官方附件上传；父题录只读，绝不覆盖既有文件。"""
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from lit.library import Library, NoRedirect, doi, exact

LIMIT=80*1024*1024


def norm(text):
    return ''.join(c for c in text.casefold() if c.isalnum())


def verify_pdf(blob, article):
    if not blob.startswith(b'%PDF-') or len(blob)>LIMIT:
        raise ValueError('文件不是 PDF 或超过大小限制')
    import fitz
    try:
        doc=fitz.open(stream=blob,filetype='pdf')
        if doc.is_encrypted or len(doc)<2:
            raise ValueError('PDF 加密或不足以确认完整研究正文')
        texts=[p.get_text() for p in doc]
        first=texts[0]
        # 只在独立章节标题处截断；摘要中的 prior references 不是参考文献节。
        front=re.split(r'^[ \t]*(?:(?:\d+(?:\.\d+)*|[IVXLCDM]+)[.)]?[ \t]+)?'
                       r'(?:references(?:[ \t]+and[ \t]+notes)?|bibliography)[ \t]*[:.]?[ \t]*$',
                       first,flags=re.I|re.M)[0]
        identifiers={x.rstrip('.,;)') for x in re.findall(r'10\.\d{4,9}/[-._;()/:a-z0-9]+',front.lower())}
        if norm(article['title']) not in norm(front[:800]) or doi(article['doi']) not in identifiers:
            raise ValueError('PDF 首页标题或 DOI 与父题录不一致')
        if re.search(r'supplementary\s+(information|material|appendix)|supporting\s+information',first[:500],re.I):
            raise ValueError('不能将补充材料作为主文 PDF')
        if sum(len(t) for t in texts)<8000 or not any(re.search(r'\b(methods|references)\b',t,re.I) for t in texts[1:]):
            raise ValueError('未确认完整正文，不能把题录或摘要算全文')
        return {'pages':len(doc),'text_characters':sum(map(len,texts)), 'sha256':hashlib.sha256(blob).hexdigest(),
                'md5':hashlib.md5(blob).hexdigest(),'bytes':len(blob),'identity':'first_page_title_and_doi',
                'pmid_mapping':'经已核 PubMed DOI 映射；不把参考文献中的标识当文章身份'}
    except ValueError:
        raise
    except Exception:
        raise ValueError('PDF 无法完整解析') from None


class AttachmentLibrary(Library):
    def post(self,path,body,headers=None):
        h={**self.headers,**(headers or {})}
        if not isinstance(body,bytes):
            body=json.dumps(body,ensure_ascii=False).encode()
            h['Content-Type']='application/json'
        h['Zotero-Write-Token']=uuid.uuid4().hex
        try:
            req=urllib.request.Request(self.base+path,data=body,headers=h,method='POST')
            with urllib.request.build_opener(NoRedirect).open(req,timeout=120) as r:
                raw=r.read()
            return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'附件写请求 HTTP {e.code}；保留现场，重跑先查已有项') from None
        except Exception:
            raise RuntimeError('附件写请求失败；状态待核，不盲重发') from None

    def file(self,key):
        req=urllib.request.Request(self.base+'/items/'+key+'/file',headers=self.headers)
        opener=urllib.request.build_opener(NoRedirect)
        try:
            try:
                with opener.open(req,timeout=120) as r: data=r.read(LIMIT+1)
            except urllib.error.HTTPError as e:
                if e.code not in (301,302,303,307,308): raise
                url=e.headers.get('Location','');u=urllib.parse.urlparse(url)
                if u.scheme!='https' or not u.hostname or not (u.hostname.endswith('.amazonaws.com') or u.hostname.endswith('.zotero.org')):
                    raise RuntimeError('附件读回目标域未验证')
                # 签名存储地址绝不继承 Zotero 密钥，不写入回执。
                with opener.open(urllib.request.Request(url),timeout=120) as r:data=r.read(LIMIT+1)
            if len(data)>LIMIT:raise RuntimeError('附件超过限制')
            return data
        except Exception:
            raise RuntimeError('附件内容无法读回；不能宣称全文已完成') from None

    def upload_bytes(self,auth,blob):
        u=urllib.parse.urlparse(auth.get('url',''))
        if u.scheme!='https' or not u.hostname or not (u.hostname.endswith('.amazonaws.com') or u.hostname.endswith('.zotero.org')):
            raise RuntimeError('上传目标域未验证')
        payload=auth['prefix'].encode()+blob+auth['suffix'].encode()
        try:
            req=urllib.request.Request(auth['url'],data=payload,headers={'Content-Type':auth['contentType']},method='POST')
            with urllib.request.build_opener(NoRedirect).open(req,timeout=180) as r:
                if r.status!=201: raise RuntimeError('未收到上传成功状态')
        except Exception:
            raise RuntimeError('附件文件上传失败；保留原题录与可重试附件') from None


def attach(lib,article,parent_key,blob,source,journal,apply=False,filename=None,verify=None):
    check=(verify or verify_pdf)(blob,article)
    before=lib.get('/items/'+parent_key)
    if not exact(before,article) or before['data'].get('deleted'):
        raise ValueError('上传前父题录身份不符或在回收站')
    children=lib.all('/items/'+parent_key+'/children')
    journal({'stage':'before','parent':before,'children':children,'pdf':check})
    # 已有附件优先验证，不能只看到条目名或 md5 就称成功。
    for child in children:
        d=child['data']
        if d.get('parentItem')!=parent_key or d.get('deleted') or d.get('itemType')!='attachment':continue
        if d.get('contentType')=='application/pdf' and d.get('md5'):
            existing=lib.file(child['key'])
            try:existing_check=verify_pdf(existing,article)
            except ValueError:continue
            return {'status':'existing_verified','key':child['key'],'pdf':existing_check}
    if not apply:return {'status':'ready','pdf':check}
    # 只重用本工具此前同来源的空壳；保留其他用户的未完成附件。
    pending=[c for c in children if c['data'].get('parentItem')==parent_key and
             c['data'].get('itemType')=='attachment' and c['data'].get('url')==source and
             c['data'].get('contentType')=='application/pdf' and not c['data'].get('md5') and
             not c['data'].get('deleted') and {'tag':'trackeep-fulltext'} in c['data'].get('tags',[])]
    if len(pending)>1:raise ValueError('有多个待完成附件，保留待核，不猜目标')
    if pending:key=pending[0]['key']
    else:
        body={'itemType':'attachment','parentItem':parent_key,'linkMode':'imported_url','title':'全文 PDF',
              'url':source,'contentType':'application/pdf','filename':filename or article['pmid']+'.pdf','tags':[{'tag':'trackeep-fulltext'}]}
        journal({'stage':'creating_attachment','parent':parent_key})
        result=lib.post('/items',[body]);success=result.get('successful',{})
        if set(success)!={'0'} or result.get('failed'):raise RuntimeError('附件创建回执不完整')
        key=success['0'].get('key','');data=success['0'].get('data',{})
        if not re.fullmatch(r'[A-Z0-9]{8}',key) or data.get('parentItem')!=parent_key or data.get('itemType')!='attachment':
            raise RuntimeError('附件创建回执关联错误，停止后续上传')
        journal({'stage':'created_attachment','key':key,'parent':parent_key})
    current=lib.get('/items/'+key)
    if current['data'].get('parentItem')!=parent_key or current['data'].get('md5'):
        raise RuntimeError('附件关联或文件状态变化，拒绝覆盖')
    headers={'Content-Type':'application/x-www-form-urlencoded','If-None-Match':'*'}
    form=urllib.parse.urlencode({'md5':check['md5'],'filename':filename or article['pmid']+'.pdf','filesize':len(blob),'mtime':int(time.time()*1000)}).encode()
    auth=lib.post('/items/'+key+'/file',form,headers)
    if not auth.get('exists'):
        lib.upload_bytes(auth,blob)
        lib.post('/items/'+key+'/file',urllib.parse.urlencode({'upload':auth['uploadKey']}).encode(),headers)
    readback=lib.file(key)
    if hashlib.sha256(readback).hexdigest()!=check['sha256']:raise RuntimeError('附件读回哈希不一致')
    (verify or verify_pdf)(readback,article)
    attachment_after=lib.get('/items/'+key)
    final_data=attachment_after['data']
    if (final_data.get('parentItem')!=parent_key or final_data.get('deleted') or
            final_data.get('contentType')!='application/pdf' or final_data.get('md5')!=check['md5']):
        raise RuntimeError('上传后附件身份、父项或哈希状态不一致')
    after=lib.get('/items/'+parent_key)
    # 挂子项可能推进父版本，但不得改其内容、标签或目录。
    clean=lambda r:{k:v for k,v in r['data'].items() if k not in ('version','dateModified')}
    if clean(before)!=clean(after):raise RuntimeError('父题录内容发生变化，须核查')
    journal({'stage':'verified','key':key,'parent_after':after,'attachment_after':attachment_after,'pdf':check})
    return {'status':'created_verified' if not pending else 'resumed_verified','key':key,'pdf':check}
