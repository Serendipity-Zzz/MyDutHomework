#include <algorithm>
#include <iomanip>
#include <iostream>
using namespace std;

struct Node {
    int data;
    Node* next;
};

// 根据数组创建带头结点的链表，头结点不存放有效数据。
Node* makeHeadList(const int a[], int n) {
    Node* head = new Node{0, nullptr};
    Node* tail = head;
    for (int i = 0; i < n; ++i) {
        tail->next = new Node{a[i], nullptr};
        tail = tail->next;
    }
    return head;
}

// 从传入的结点开始打印；打印数据时应传入 head->next。
void printList(const Node* p) {
    while (p) {
        cout << p->data;
        if (p->next) cout << " -> ";
        p = p->next;
    }
    cout << '\n';
}

void destroyList(Node* head) {
    while (head) {
        Node* old = head;
        head = head->next;
        delete old;
    }
}

// 第一题：快指针先走 k 步，再和慢指针同步前进。
// 时间 O(n)，辅助空间 O(1)。head 指向头结点。
const Node* kthFromEnd(const Node* head, int k) {
    if (!head || k <= 0) return nullptr;
    const Node* fast = head->next;
    const Node* slow = head->next;
    for (int i = 0; i < k; ++i) {
        if (!fast) return nullptr;
        fast = fast->next;
    }
    while (fast) {
        fast = fast->next;
        slow = slow->next;
    }
    return slow;
}

// 第二题：以下函数的 head 指向第一个数据结点。
// 求最大值和平均值时，要求链表非空；预设数据满足此条件。
int recursiveMax(const Node* head) {
    if (!head->next) return head->data;
    return max(head->data, recursiveMax(head->next));
}

int recursiveCount(const Node* head) {
    if (!head) return 0;
    return 1 + recursiveCount(head->next);
}

long long recursiveSum(const Node* head) {
    if (!head) return 0;
    return head->data + recursiveSum(head->next);
}

// 递归求和、递归计数，再用浮点除法计算平均值。
// 各运算时间 O(n)，递归栈空间 O(n)。
double recursiveAverage(const Node* head) {
    return static_cast<double>(recursiveSum(head)) / recursiveCount(head);
}

// 第三题：A、B 为互不相交、带头结点的递增链表。
// 每次取较小结点，头插到 C；C 复用 A 的头结点。
// 时间 O(m+n)，辅助空间 O(1)，不创建新结点。
Node* mergeDescending(Node*& A, Node*& B) {
    Node* p = A->next;
    Node* q = B->next;
    Node* C = A;
    C->next = nullptr;
    B->next = nullptr;
    A = nullptr;  // 原 A 的头结点已交给 C。
    while (p || q) {
        Node* chosen;
        if (!q || (p && p->data <= q->data)) {
            chosen = p;
            p = p->next;
        } else {
            chosen = q;
            q = q->next;
        }
        chosen->next = C->next;
        C->next = chosen;
    }
    return C;
}

int main() {
    // 第一题：预设链表，查找倒数第 2 个结点。
    int a1[] = {10, 20, 30, 40, 50};
    Node* H = makeHeadList(a1, 5);
    int k = 2;
    cout << "第一题，链表：";
    printList(H->next);
    const Node* result = kthFromEnd(H, k);
    if (result) cout << "倒数第 " << k << " 个结点的值：" << result->data << '\n';
    else cout << "未找到该结点\n";
    destroyList(H);

    

    // 第二题：跳过头结点，将首个数据结点传给递归函数。
    int a2[] = {3, 7, -2, 10, 5};
    Node* L = makeHeadList(a2, 5);
    cout << "\n第二题，链表：";
    printList(L->next);
    cout << "最大值：" << recursiveMax(L->next) << '\n';
    cout << "结点个数：" << recursiveCount(L->next) << '\n';
    cout << "平均值：" << fixed << setprecision(2)
         << recursiveAverage(L->next) << '\n';
    destroyList(L);

    // 第三题：预设两个递增链表，归并为递减链表。
    int a3[] = {1, 3, 5, 7};
    int b3[] = {2, 3, 6, 8};
    Node* A = makeHeadList(a3, 4);
    Node* B = makeHeadList(b3, 4);
    cout << "\n第三题\nA：";
    printList(A->next);
    cout << "B：";
    printList(B->next);
    Node* C = mergeDescending(A, B);
    cout << "C：";
    printList(C->next);
    destroyList(C);
    destroyList(B);  // B 仅剩头结点；A 已为 nullptr，无需再释放。
    return 0;
}
