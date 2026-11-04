#include <iostream>
#include <queue>
#include <stack>
#include <vector>
using namespace std;

// 第三次课作业：二叉树。
struct Node {
    int data;
    Node* left;
    Node* right;
};

class BinaryTree {
    Node* root;

    // 数组按完全二叉树的位置排列，-1 表示该位置没有结点。
    Node* create(const int a[], int n, int i) {
        if (i >= n || a[i] == -1) return nullptr;
        Node* p = new Node{a[i], nullptr, nullptr};
        p->left = create(a, n, 2 * i + 1);
        p->right = create(a, n, 2 * i + 2);
        return p;
    }

    void destroy(Node* p) {
        if (p == nullptr) return;
        destroy(p->left);
        destroy(p->right);
        delete p;
    }

    // 递归统计各层结点数，并记录其中的最大值。
    void countWidth(Node* p, int level, vector<int>& counts, int& result) {
        if (p == nullptr) return;
        ++counts[level];
        if (counts[level] > result) result = counts[level];
        countWidth(p->left, level + 1, counts, result);
        countWidth(p->right, level + 1, counts, result);
    }

public:
    BinaryTree(const int a[], int n) {
        root = create(a, n, 0);
    }

    ~BinaryTree() {
        destroy(root);
    }

    Node* getRoot() {
        return root;
    }

    // 第一题：层次遍历。
    void levelOrder() {
        if (root == nullptr) return;
        queue<Node*> q;
        q.push(root);
        while (!q.empty()) {
            Node* p = q.front();
            q.pop();
            cout << p->data << ' ';
            if (p->left != nullptr) q.push(p->left);
            if (p->right != nullptr) q.push(p->right);
        }
    }

    // 递归先序遍历：根、左、右。
    void preOrderRecursive(Node* p) {
        if (p == nullptr) return;
        cout << p->data << ' ';
        preOrderRecursive(p->left);
        preOrderRecursive(p->right);
    }

    // 非递归先序遍历：右孩子先入栈，左孩子后入栈。
    void preOrderIterative() {
        if (root == nullptr) return;
        stack<Node*> s;
        s.push(root);
        while (!s.empty()) {
            Node* p = s.top();
            s.pop();
            cout << p->data << ' ';
            if (p->right != nullptr) s.push(p->right);
            if (p->left != nullptr) s.push(p->left);
        }
    }

    // 递归中序遍历：左、根、右。
    void inOrderRecursive(Node* p) {
        if (p == nullptr) return;
        inOrderRecursive(p->left);
        cout << p->data << ' ';
        inOrderRecursive(p->right);
    }

    // 非递归中序遍历。
    void inOrderIterative() {
        stack<Node*> s;
        Node* p = root;
        while (p != nullptr || !s.empty()) {
            while (p != nullptr) {
                s.push(p);
                p = p->left;
            }
            p = s.top();
            s.pop();
            cout << p->data << ' ';
            p = p->right;
        }
    }

    // 第二题：递归统计度为 1 的结点数。
    int degree1(Node* p) {
        if (p == nullptr) return 0;
        int count = 0;
        if ((p->left != nullptr && p->right == nullptr)
            || (p->left == nullptr && p->right != nullptr))
            count = 1;
        return count + degree1(p->left) + degree1(p->right);
    }

    // 递归统计度为 2 的结点数。
    int degree2(Node* p) {
        if (p == nullptr) return 0;
        int count = 0;
        if (p->left != nullptr && p->right != nullptr) count = 1;
        return count + degree2(p->left) + degree2(p->right);
    }

    // 递归统计度为 0 的结点数，即叶结点数。
    int degree0(Node* p) {
        if (p == nullptr) return 0;
        if (p->left == nullptr && p->right == nullptr) return 1;
        return degree0(p->left) + degree0(p->right);
    }

    // 递归求高度，空树高度为 0，单结点树高度为 1。
    int height(Node* p) {
        if (p == nullptr) return 0;
        int leftHeight = height(p->left);
        int rightHeight = height(p->right);
        return (leftHeight > rightHeight ? leftHeight : rightHeight) + 1;
    }

    // 通过递归辅助函数求宽度，即各层结点数中的最大值。
    int width() {
        vector<int> counts(height(root) + 1, 0);
        int result = 0;
        countWidth(root, 1, counts, result);
        return result;
    }

    // 第三题：层次扫描时，出现空位置后不能再出现非空结点。
    bool isComplete() {
        queue<Node*> q;
        q.push(root);
        bool seenNull = false;
        while (!q.empty()) {
            Node* p = q.front();
            q.pop();
            if (p == nullptr) {
                seenNull = true;
            } else {
                if (seenNull) return false;
                q.push(p->left);
                q.push(p->right);
            }
        }
        return true;
    }
};

int main() {
    int a[] = {8, 7, 5, -1, 10, 12, 6};
    BinaryTree tree(a, 7);

    cout << "层次遍历：";
    tree.levelOrder();
    cout << "\n递归先序遍历：";
    tree.preOrderRecursive(tree.getRoot());
    cout << "\n非递归先序遍历：";
    tree.preOrderIterative();
    cout << "\n递归中序遍历：";
    tree.inOrderRecursive(tree.getRoot());
    cout << "\n非递归中序遍历：";
    tree.inOrderIterative();
    cout << '\n';

    cout << "度为1的结点个数：" << tree.degree1(tree.getRoot()) << '\n';
    cout << "度为2的结点个数：" << tree.degree2(tree.getRoot()) << '\n';
    cout << "度为0的结点个数：" << tree.degree0(tree.getRoot()) << '\n';
    cout << "二叉树高度：" << tree.height(tree.getRoot()) << '\n';
    cout << "二叉树宽度：" << tree.width() << '\n';

    if (tree.isComplete()) cout << "是完全二叉树\n";
    else cout << "不是完全二叉树\n";
    return 0;
}
