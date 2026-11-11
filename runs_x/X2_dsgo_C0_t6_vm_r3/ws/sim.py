import sys

def parse(path):
    prog=[]
    for line in open(path):
        line=line.split(';',1)[0].strip()
        if not line:
            continue
        prog.append(line.split())
    return prog

def run(prog, limit=100000000):
    regs={'a':0,'b':0,'c':0,'d':0}
    def val(x):
        if x in regs:
            return regs[x]
        return int(x)
    pc=0
    out=[]
    count=0
    while 0<=pc<len(prog):
        ins=prog[pc]
        op=ins[0]
        count+=1
        if count>limit:
            raise Exception('limit')
        nxt=pc+1
        if op=='set':
            regs[ins[1]]=val(ins[2])%65536
        elif op=='add':
            regs[ins[1]]=(regs[ins[1]]+val(ins[2]))%65536
        elif op=='mul':
            regs[ins[1]]=(regs[ins[1]]*val(ins[2]))%65536
        elif op=='mod':
            x=val(ins[2])
            if x>0:
                regs[ins[1]]=regs[ins[1]]%x
        elif op=='dec':
            regs[ins[1]]=max(0,regs[ins[1]]-1)
        elif op=='jnz':
            if val(ins[1])!=0:
                nxt=pc+val(ins[2])
        elif op=='skp':
            if val(ins[1])<val(ins[2]):
                nxt=pc+2
        elif op=='out':
            out.append(val(ins[1]))
        else:
            raise Exception('bad '+op)
        pc=nxt
    return out,count,regs

prog=parse('prog.pw9')
out,count,regs=run(prog)
print('instructions:',len(prog))
print('count:',count)
print('num out:',len(out))
print('sum:',sum(out))
print('regs:',regs)
print('first 30:',out[:30])
print('last 30:',out[-30:])
