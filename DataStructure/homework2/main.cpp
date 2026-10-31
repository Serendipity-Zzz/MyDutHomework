#include <iostream>
#include <queue>
#include <stack>
using namespace std;

// 第一题：用两个栈计算四则运算表达式。
int priority(char op) {
    if (op == '~') return 3;
    if (op == '+' || op == '-') return 1;
    if (op == '*' || op == '/') return 2;
    return 0;
}

void calculateTop(stack<double>& numbers, stack<char>& operators) {
    char op = operators.top();
    operators.pop();
    double right = numbers.top();
    numbers.pop();
    if (op == '~') { 
        numbers.push(-right);
        return;
    }
    double left = numbers.top();
    numbers.pop();

    if (op == '+') numbers.push(left + right);
    else if (op == '-') numbers.push(left - right);
    else if (op == '*') numbers.push(left * right);
    else if (op == '/') numbers.push(left / right);
}

double calculate(const char expression[]) {
    stack<double> numbers;
    stack<char> operators;
    bool expectNumber = true; 

    for (int i = 0; expression[i] != '\0'; ++i) {
        char c = expression[i];
        if (c == ' ') continue;
//转数字
        if (c >= '0' && c <= '9') {
            numbers.push(c - '0'); 
            expectNumber = false;
        } else if (c == '(') {
            operators.push(c);
            expectNumber = true;
        } else if (c == ')') {
            while (operators.top() != '(')
                calculateTop(numbers, operators);
            operators.pop();
            expectNumber = false;
        } else if (expectNumber && (c == '+' || c == '-')) {
            if (c == '-') operators.push('~');  
        } else {
            while (!operators.empty() && operators.top() != '('
                   && priority(operators.top()) >= priority(c)) {
                calculateTop(numbers, operators);
            }
            operators.push(c);
            expectNumber = true;
        }
    }

    while (!operators.empty())
        calculateTop(numbers, operators);
    return numbers.top();
}
// 第二题
// 约定 k>=2，k<=66 时各系数不溢出
void printCoefficients(int k) {
    queue<long long> coefficients;
    coefficients.push(1);  // 第 0 行只有一个系数 1

    for (int row = 1; row <= k; ++row) {
        int length = static_cast<int>(coefficients.size());
        long long previous = 0;

        for (int j = 0; j < length; ++j) {
            long long current = coefficients.front();
            coefficients.pop();
            coefficients.push(previous + current);
            previous = current;
        }
        coefficients.push(previous);  // 补右侧 1
    }

    // 第 j 个系数对应 a^(k-j) * b^j，j 从 0 开始。
    for (int j = 0; j <= k; ++j) {
        if (j > 0) cout << ' ';
        cout << coefficients.front();
        coefficients.pop();
    }
    cout << '\n';
}
// 时间 O(k^2)，辅助空间 O(k)。

// 第三题
int lastOccurrence(const char str[], const char substr[]) {
    int n = 0,m = 0;

    while (str[n] != '\0') ++n;
    while (substr[m] != '\0') ++m;
    if (m == 0) return -1;  // 空字串不参与

    for (int i = n - m; i >= 0; --i) {
        int j = 0;
        while (j < m && str[i + j] == substr[j])
            ++j;
        if (j == m) return i;  // 从右向左找到的第一个，就是最后一次出现。
    }
    return -1;
}

int main() {
    // 第一题
    const char expression[] = "3*(7-2*2)+8/4";
    cout << "第一题：四则运算计算器\n";
    cout << "表达式：" << expression << '\n';
    cout << "计算结果：" << calculate(expression) << '\n';

    // 第二题：k=5，预期系数为 1 5 10 10 5 1。
    int k = 5;
    cout << "\n第二题：(a+b)^" << k << " 的展开系数\n";
    cout << "按照 a 的降幂、b 的升幂排列：";
    printCoefficients(k);

    // 第三题：abc 出现在下标 2、5，预期最后一次的位置为 5。
    const char str[] = "ababcabcab";
    const char substr[] = "abc";
    cout << "\n第三题：查找子串最后一次出现的位置\n";
    cout << "主串：" << str << '\n';
    cout << "子串：" << substr << '\n';
    int position = lastOccurrence(str, substr);
    if (position == -1) {
        cout << "未找到子串\n";
    } else {
        cout << "最后一次出现的下标：" << position << "（从 0 开始）\n";
        cout << "对应主串的第 " << position + 1 << " 个字符\n";
    }
    return 0;
}
