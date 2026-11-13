"""Very small sanity check for Lua sources: block keywords vs. 'end', brackets, strings."""
import re, sys

def strip(src):
    out=[];i=0;n=len(src)
    while i<n:
        if src.startswith('--[[',i):
            j=src.find(']]',i); i=j+2; continue
        if src.startswith('--',i):
            j=src.find('\n',i); i=n if j<0 else j; continue
        c=src[i]
        if c in '"\'':
            j=i+1
            while j<n and src[j]!=c:
                if src[j]=='\\': j+=1
                if src[j]=='\n': raise SyntaxError('unterminated string at %d'%src.count('\n',0,i))
                j+=1
            out.append(' ""'); i=j+1; continue
        if src.startswith('[[',i):
            j=src.find(']]',i); i=j+2; out.append(' ""'); continue
        out.append(c); i+=1
    return ''.join(out)

def check(src):
    s=strip(src)
    depth=0; stack=[]
    for m in re.finditer(r'\b(function|if|for|while|do|repeat|until|end|then|elseif|else)\b|[(){}\[\]]',s):
        t=m.group(0); line=s.count('\n',0,m.start())+1
        if t in ('function','if','repeat'):
            stack.append((t,line))
        elif t in ('for','while'):
            stack.append((t,line))  # their 'do' is consumed below
        elif t=='do':
            if stack and stack[-1][0] in ('for','while') and not stack[-1][0].endswith('_do'):
                stack[-1]=(stack[-1][0]+'_do',stack[-1][1])
            else:
                stack.append(('do',line))
        elif t=='end':
            if not stack: raise SyntaxError('unexpected end at line %d'%line)
            k=stack.pop()
            if k[0]=='repeat': raise SyntaxError('end closes repeat at %d'%line)
        elif t=='until':
            k=stack.pop()
            if k[0]!='repeat': raise SyntaxError('until mismatch at %d'%line)
        elif t in '([{':
            stack.append((t,line))
        elif t in ')]}':
            k=stack.pop(); pair={'(' :')','[':']','{':'}'}
            if pair.get(k[0])!=t: raise SyntaxError('bracket mismatch %s at %d (opened %s line %d)'%(t,line,k[0],k[1]))
    if stack: raise SyntaxError('unclosed %r'%(stack[-5:],))
    return True

if __name__=='__main__':
    for p in sys.argv[1:]:
        check(open(p,encoding='latin-1').read()); print('ok',p)
