# Pointer and Smart Pointer

## Pointer

A pointer is a group of memory cells that can hold an address.

The operator `&` gives an address to an object, so the statement `p = &c;` assigns the address of `c` to the variable `p`, or `p` points to `c`

The operator `*` is the **indirection** or **dereferencing** operator, meaning if applied to pointer, it accesses the object the pointer points to

Consider

``` c
int x = 1, y = 2, z[10];
int *ip;

ip = &x; // ip points to x
y = *ip; // y is now 1
*ip = 0; // x is now 0
ip = &z[0]; // ip now points to z[0]
```

The below example outputs the same result

``` c
y = *ip + 1 // increments whatever ip points to by 1
++*ip
(*ip)++ // if parentheses are ommitted, it will increment ip as variable instead
```

## Pointer as Arguments

Since C passes arguments to functions by value, it's not enough to use variables as functions' parameters

Consider a `swap` function that performs type casting

Normally, we would write

``` c
void swap(int x, int y) {
    int tmp;

    tmp = x;
    x = y;
    y = tmp;
}
```

Because of call by value, this function can't affect the arguments in the routine that calls it; it only swaps copies of `x` and `y`

To obtain the desired behavior, we pass pointers as parameters

``` c
void swap(int *px, int *py) {
    int tmp;

    tmp = *px;
    *px = *py;
    *py = tmp;
}

swap(&a, &b);
```

Now, consider the function `getint` that performs free-format input conversion

We want to input a stream of inputs, break them and convert them into integer one by one

Then, signal `EOF` when there's no input

We can use a pointer as parameter

The function would be

``` c
#include <ctype.h>

int getint(int *pn) {
    int c, sign;

    while (isspace(c = getch())) {
        ; // skip white type
    }

    // validate if c is a number
    if (!isdigit(c) && c != EOF &&  c != '+' && c != '-') {
        ungetch(c);
        return 0;
    }

    if (c == '-') {
        sign = -1;
    } else {
        sign = 1;
    }

    if (c == '+' || c == '-') {
        c = getch();
    }

    for (*pn = 0; isdigit(c); c = getch()) {
        *pn *= 10;
        *pn += (c - '0');
    }

    *pn *= sign;

    if (c != EOF) {
        ungetch(c);
    }

    return c;
}
```

## Pointers and Arrays

If `pa` is a pointer to an integer, declared as `int *pa;`, then the assignment `pa = &a[0];` sets `pa` to point to element zero of `a`; that is, `pa` contains the address of `a[0]`

Now the assignment `x = *pa;` will copy the contents of `a[0]` into `x`

If `pa` points to a particular element of an array, then by definition `pa + 1` points to the next element, `pa + i` points `i` elements after `pa`, and `pa - i` points `i` elements before

Thus, if `pa` points to `a[0]`, `*(pa+1)` refers to the contents of `a[1]`, `pa + i` is the address of `a[i]`, and `*(pa + i)` is the contents of `a[i]`

By definition, the value of a variable or expression of type array is the address of element zero of the array.

