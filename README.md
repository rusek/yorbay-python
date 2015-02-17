# Yorbay

Yorbay is a localization framework based on l20n file format. Although written in Python, this library is heavily influenced by original [l20n.js](https://github.com/l20n/l20n.js) project.

## Hello, world!

The easiest way to use Yorbay is to create `Context` object, using one of its class methods:

```python
from yorbay import Context

tr = Context.from_string("""
    <hello "Hello, world!">
""")

print tr('hello')
```

You can directly specify additional parameters that will be used when formatting an entity:
```python
tr = Context.from_string("""
<plural($n) { $n == 1 ? "one" : "other" }>

<newMessages[plural($n)] {
    one: "You have a new message",
    other: "You have {{$n}} new messages"
}>
""")

print tr('newMessages', n=3)
```

You can also set context-wise variables, if you really want to:
```python
tr['n'] = 3
print tr('newMessages')
```

## Loading translations from files

Defining l20n source inline in scripts isn't practical in real cases. Instead of creating the context from string, there are other ways to obtain `Context` instance. If all you want to do is to load messages from a single file, then you can call `Context.from_file(path)`, where `path` specifies the location of translation file.

However, the most convenient way is to use yorbay translation autodiscovery mechanism:

```python
from yorbay import Context

tr = Context.from_module(__name__)
print tr('hello')
```

Yorbay first looks for `locale` directory inside the directory containing the specified module. If it's not found, the library examines the directory of the parent module and so on, until `locale` directory is found.

`locale` directory should contain translation files for supported languages, like `en.l20n` or `de_DE.l20n`. The complete directory structure of a sample project is as follows:

```
myproject/
    locale/
        de.l20n
        en.l20n
        en_GB.l20n
        pl.l20n
    myscript.l20n
```

## Debug mode

Debug mode is a work in progress:

```python
from yorbay import Context
from yorbay.debug.stacktrace import format_exception

def error_hook(exc_type, exc_value, tb):
    print format_exception(exc_value),

tr = Context.from_file("messages.l20n", error_hook=error_hook, debug=True)
print tr("hello")

```

In `messages.l20n`:

```
<yorbay {short: "Yorbay", long: "Yorbay translation framework"}>

<hello "Hello, {{yorbay}}!">
```

Should output something like:
```
Traceback (most recent call last):
  File /home/yorbay/messages.l20n, line 3 in entity hello
    <hello "Hello, {{yorbay}}!">
  File /home/yorbay/messages.l20n, line 1 in entity yorbay
    <yorbay {short: "Yorbay", long: "Yorbay translation framework"}>
KeyError: 'Hash key lookup failed'
Hello, {{yorbay}}!

```
