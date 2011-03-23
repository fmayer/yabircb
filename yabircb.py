# -*- coding: utf-8 -*-

# Copyright (c) 2011, Florian Mayer <flormayer@aim.com>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Use this software for good, not for evil.

from __future__ import with_statement

import sys
import cmath

# twisted imports
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol

NULLITER = iter([])
DEFAULTENC = 'utf-8'

ACTION = 1
MESSAGE = 2

def maybe_int(num):
    if not num % 1:
        return int(num)
    return num


def find_prev(itr, idx, elem):
    for idx in xrange(idx, -1, -1):
        if itr[idx] == elem:
            return idx
    return -1


class Handler(object):
    def privmsg(self, user, channel, msg):
        return NULLITER
   
    def action(self, user, channel, msg):
        return NULLITER


class StartsWith(Handler):
    def __init__(self, startfun, child):
        self.startfun = startfun
        self.child = child
    
    def privmsg(self, user, channel, msg, bot):
        start = self.startfun(user=user, channel=channel, msg=msg, bot=bot)
        
        if msg.startswith(start):
            return self.child.privmsg(user, channel,  msg[len(start):], bot)
        else:
            return NULLITER 


class Dispatch(Handler):
    def __init__(self, children, fallback=None):
        self.children = children
        self.fallback = fallback
    
    def privmsg(self, user, channel, msg, bot):
        split = msg.split(None, 1)
        disp = split[0]
        if not disp:
            return NULLITER
        if len(split) == 2:
            rest = split[1]
        else:
            rest = ''
        try:
            return self.children[disp].privmsg(
                user, channel, rest, bot)
        except KeyError:
            if self.fallback is None:
                return NULLITER
            else:
                return self.fallback.privmsg(user, channel, rest, bot)


class Respond(Handler):
    def __init__(self, child):
        self.child = child
    
    def privmsg(self, user, channel, msg, bot):
        nick = user.split('!', 1)[0]
        for activity, user, message, length in self.child.privmsg(
            user, channel, msg, bot
        ):
            yield activity, user, "%s: %s"  % (nick, message), length


class Static(Handler):
    def __init__(self, text):
        self.text = text
    
    def privmsg(self, user, channel, msg, bot):
        return [(MESSAGE, channel, self.text, irc.MAX_COMMAND_LENGTH)]


class To(Handler):
    def __init__(self, child):
        self.child = child
    
    def privmsg(self, user, channel, msg, bot):
        split = msg.split(None, 1)
        name = split[0]
        if len(split) == 2:
            rest = split[1]
        else:
            rest = ''
        return self.child.privmsg(name, channel, rest, bot)


def calc_rpn(expr, operators):
    stack = []
    
    for item in expr:
        if item in operators:
            n, fun = operators[item]
            if len(stack) >= n:
                arguments = stack[-n:]
                stack = stack[:-n]
                stack.append(fun(*arguments))
            else:
                raise ValueError(
                    '%s expected %d parameters, got %d' % (item, n, len(stack))
                )
        else:
            stack.append(item)
    
    if len(stack) == 1:
        return stack[0]
    else:
        raise ValueError('Got too many values')


class RPN(Handler):
    def __init__(self, mem=None):
        self.mem = mem
    
    def privmsg(self, user, channel, msg, bot):
        operators = {
            u'+': (2, lambda x, y: x + y),
            u'-': (2, lambda x, y: x - y),
            u'*': (2, lambda x, y: x * y),
            u'/': (2, lambda x, y: x / y),
            u'sqrt': (1, cmath.sqrt),
            u'√': (1, cmath.sqrt),
            u'pow': (2, lambda x, y: x ** y),
            u'sin': (1, cmath.sin),
            u'cos': (1, cmath.cos),
            u'tan': (1, cmath.tan),
            u'asin': (1, cmath.asin),
            u'acos': (1, cmath.acos),
            u'atan': (1, cmath.atan),
            
            u'deg': (1, lambda x: 180. * x / cmath.pi),
            u'rad': (1, lambda x: cmath.pi * x / 180),
            
            u'=': (2, lambda x, y: x == y),
            u'!=': (2, lambda x, y: x != y),
            u'≠': (2, lambda x, y: x != y),
            u'not': (1, lambda x: not x),
            u'and': (2, lambda x, y: x and y),
            u'or': (2, lambda x, y: x or y),
            u'<': (2, lambda x, y: x < y),
            u'<=': (2, lambda x, y: x <= y),
            u'≤': (2, lambda x, y: x <= y),
            u'>': (2, lambda x, y: x > y),
            u'>=': (2, lambda x, y: x >= y),
            u'≥': (2, lambda x, y: x >= y),
            
            u'ft': (1, lambda x: x * 0.3048),
            u'in': (1, lambda x: x * 0.0254),
            u'km': (1, lambda x: x * 1000),
            u'm': (1, lambda x: x),
            u'mile': (1, lambda x: x * 1609.344),
            u'doppelmaß': (1, lambda x: x * 2),
            u'seidl': (1, lambda x: x * 0.354),
            
            u'toft': (1, lambda x: x / 0.3048),
            u'toin': (1, lambda x: x / 0.0254),
            u'tokm': (1, lambda x: x / 1000),
            u'tom': (1, lambda x: x),
            u'tomile': (1, lambda x: x / 1609.344),
            u'todoppelmaß': (1, lambda x: x / 2),
            u'toseidl': (1, lambda x: x / 0.354),
        }
        
        constants = {
            u'pi': cmath.pi,
            u'π': cmath.pi,
            u'e': cmath.e,
            u'@': self.mem,
            u'j': 1j,
            u'True': True,
            u'False': False,
            u'∞': float('inf'),
        }
            
        expr = []
        for elem in msg.replace('(', '').replace(')', '').split():
            if elem in operators:
                expr.append(elem)
            elif elem in constants:
                expr.append(constants[elem])
            else:
                try:
                    expr.append(float(elem))
                except ValueError:
                    return [
                        (MESSAGE,
                         channel,
                         ('%s is neither an operator, '
                         'nor a constant, nor a number.' % elem),
                         irc.MAX_COMMAND_LENGTH)
                    ]
        
        try:
            result = calc_rpn(expr, operators)
            if isinstance(result, complex):
                if not result.imag:
                    result = result.real
            else:
                result = maybe_int(result)
            self.mem = result
            result = str(result)
        except ValueError, e:
            result = 'Error: %s' % e.args[0]
        except OverflowError:
            result = 'Error: Overflow.'
        except ZeroDivisionError:
            result = 'Error: division by zero.'
        
        return [
            (MESSAGE,
             channel,
             result,
             irc.MAX_COMMAND_LENGTH)
        ]


class Wrap(Handler):
    def __init__(self, privmsg=None, action=None):
        if privmsg is None:
            privmsg = self._dummy
        if action is None:
            action = self._dummy
        
        self.privmsg = privmsg
        self.action = action
    
    @staticmethod
    def _dummy(*args, **kwargs):
        return NULLITER


class More(Handler):
    def __init__(self, child, maxlength, cont='...'):
        self.child = child
        self.maxlength = maxlength
        self.cont = cont
        
        self.cache = []
    
    def privmsg(self, user, channel, msg, bot):
        ret = list(self.child.privmsg(user, channel, msg, bot))
        remaining = self.maxlength
        if ret:
            self.cache = []
            for value in ret:
                print value
                
                if not remaining:
                    self.cache.append(value)
                    continue
                
                activity, user, message, length = value
                if len(message) > remaining:
                    nrem = find_prev(message, remaining, ' ')
                    if nrem > 0:
                        remaining = nrem
                    yield (
                        activity, user,
                        message[:remaining].strip() + self.cont, length
                    )
                    self.cache.append(
                        (activity, user, message[remaining:], length)
                    )
                    remaining = 0
                else:
                    yield activity, user, message, length
                    remaining -= len(message)
    
    def more(self, *args, **kwargs):
        remaining = self.maxlength
        
        newcache = []
        for value in self.cache:
            if not remaining:
                newcache.append(value)
            
            activity, user, message, length = value
            if len(message) > remaining:
                nrem = find_prev(message, remaining, ' ')
                if nrem > 0:
                    remaining = nrem
                yield activity, user, message[:remaining].strip() + self.cont, length
                newcache.append(
                    (activity, user, message[remaining:], length)
                )
            else:
                yield activity, user, message, length
                remaining -= len(message)
        self.cache = newcache
    
    def wrap_more(self):
        return Wrap(self.more, self.more)


class GeneralBot(irc.IRCClient):
    def signedOn(self):
        for key in self.factory.channels.iterkeys():
            self.join(key)

    def privmsg(self, user, channel, msg):
        message = msg.decode(
            self.factory.channels.get(
                channel, self.factory.defaultenc))
        
        for handler in self.factory.handlers:
            for result in handler.privmsg(user, channel, message, self):
                if result is None:
                    continue
                activity = result[0]
                if activity == ACTION:
                    self.uniaction(*result[1:])
                else:
                    self.unimsg(*result[1:])
    
    def uniaction(self, user, message, length=irc.MAX_COMMAND_LENGTH):
        message = message.encode(
            self.factory.channels.get(
                user[1:], self.factory.defaultenc))
        self.action(user, message, length)
    
    def unimsg(self, user, message, length=irc.MAX_COMMAND_LENGTH):
        message = message.encode(
            self.factory.channels.get(
                user[1:], self.factory.defaultenc))
        self.msg(user, message, length)


class GeneralBotFactory(protocol.ClientFactory):
    # the class of the protocol to build when new connection is made
    protocol = GeneralBot

    def __init__(self, channels, nickname, handlers, defaultenc=DEFAULTENC):
        self.channels = channels
        self.nickname = nickname
        
        self.handlers = handlers
        self.defaultenc = defaultenc

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print "connection failed:", reason
        reactor.stop()
    
    def buildProtocol(self, addr):
        obj = protocol.ClientFactory.buildProtocol(self, addr)
        obj.nickname = self.nickname
        return obj


if __name__ == '__main__':
    # python neobot.py NAME SERVER PORT CHANNEL ENCODING ...]
    # create factory protocol and application   
    liter = iter(sys.argv[4:])
    static = More(
        Static(u'Fine chariot, but where are ze horses?'), 20, ' [!more]'
    )
    main = Dispatch(
        {u'chariot': Respond(static),
         u'analyze': Respond(Static('A strange game. The only winning move is '
                            'not to play.')),
         u'more': Respond(static.wrap_more()),
         u'rpn': Respond(RPN()),},
        Static(u'What do you want‽')
    )
    
    tell = To(main)
    main.children['to'] = tell
    
    f = GeneralBotFactory(
        dict(zip(liter, liter)), sys.argv[1],
        [StartsWith(lambda **kw: '!', main),
         StartsWith(lambda **kw: kw['bot'].nickname + ': ', main)]
    )

    # connect factory to this host and port
    reactor.connectTCP(sys.argv[2], int(sys.argv[3]), f)

    # run bot
    reactor.run()
