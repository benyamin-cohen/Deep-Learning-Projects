import copy
import numpy as np
import pickle

GOAL = "demand"


class Node:
    """This class represents the nodes of the trees, where the data is the
    value (for leaves) or attribute otherwise, choices represents the path"""
    def __init__(self, data, choices=None, depth=0):
        self.data = data
        self.choices = choices
        self.children = []
        self.depth = depth

    def __del__(self):
        for child in self.children:
            del child
        del self.children


class Tree:
    def __init__(self, records_df, limit=0, attributes=None, goal=GOAL, name=""):
        """creates the tree based on a dictionary of attributes and options"""
        self.limit = limit
        self.goal = goal
        self.name = name
        if records_df is not None:
            self.rows = len(records_df)
            self.root = self.create_tree(records_df, attributes)
        else:
            self.rows = 0
            self.root = Node(None)

    def __del__(self):
        del self.root

    def create_tree(self, records_df, attributes=None):
        """creates the tree and returns the root"""
        if not attributes:
            attributes = list(records_df.columns)
            attributes.remove(self.goal)
        return self.recursive_build(records_df, attributes, [], 0)

    def recursive_build(self, records_df, attributes, path, depth):
        """Recursive helper to build the tree"""
        if self.limit and self.limit <= depth:
            attribute = None
        else:
            attribute = self.get_next_attribute(attributes, records_df)
            while attribute and len(records_df[attribute].value_counts()) == 1:
                attributes.remove(attribute)
                attribute = self.get_next_attribute(attributes, records_df)
        if not attribute:
            attribute = self.goal
        if attribute != self.goal:
            attributes.remove(attribute)
            if not path:
                node = Node(attribute, depth=depth)
            else:
                node = Node(attribute, path, depth)
            children = []
            for val in records_df[attribute].unique():
                new_data = records_df[records_df[attribute] == val]
                new_path = copy.deepcopy(path + [(attribute, val)])
                records_df = records_df[records_df[attribute] != val]
                remaining = copy.deepcopy(attributes)
                children.append(self.recursive_build(new_data, remaining,
                                                     new_path, depth + 1))
            node.children = children
        else:
            node = Node(self.decide_leaf(records_df), path, depth=depth)
        return node

    def get_next_attribute(self, attribute_list, records_df):
        """returns the next attribute"""
        if attribute_list:
            return attribute_list[0]
        else:
            return None

    def decide_leaf(self, records_df):
        """Decide the value of the leaf based on the records"""
        if records_df.empty:
            return None
        return records_df[self.goal].value_counts().argmax()

    def pruning(self, records_df, threshold):
        """Prunes the tree based on a threshold"""
        nodes_to_check = [self.root]
        while nodes_to_check:
            node = nodes_to_check.pop()
            children_remove = []
            children_append = []
            for child in node.children:
                path = child.choices
                depth = child.depth
                relevant = copy.deepcopy(records_df)
                for attribute, value in path:
                    relevant = relevant[relevant[attribute] == value]
                if len(relevant) / self.rows <= threshold:
                    children_remove.append(child)
                    children_append.append(Node(self.decide_leaf(relevant),
                                              path, depth=depth))
                else:
                    nodes_to_check.append(child)
            for child in children_remove:
                node.children.remove(child)
            for child in children_append:
                node.children.append(child)

    def get_val(self, row):
        """Gets the relevant node based on the row"""
        node = self.root
        while node:
            prev_node = node
            if not len(node.children):
                return node.data
            if node.data not in row.keys():
                return None
            children = prev_node.children
            for child in children:
                if row[prev_node.data] == child.choices[-1][1]:
                    node = child
                    break
                else:
                    node = None
        return None

    def save_tree(self, output_path):
        """Saves the tree"""
        with open(output_path, 'wb') as file:
            pickle.dump(self, file)

    def load_tree(self, path):
        """Saves the tree"""
        with open(path, 'rb') as file:
            node = pickle.load(file)
        self.root = node.root
        self.name = node.name
        self.goal = node.goal
        self.rows = node.rows
        self.limit = node.limit


class EntropyTree(Tree):
    def get_next_attribute(self, attribute_list, records_df):
        """returns the attribute with the minimum entropy"""
        entropy = calc_entropy(attribute_list, records_df)
        entropy = {k: v for k, v in entropy.items() if v}
        if len(entropy):
            return min(entropy, key=entropy.get)
        return None


class InformationGainTree(Tree):
    def get_next_attribute(self, attribute_list, records_df):
        """Returns the attribute with the highest information gain"""
        info_gain = information_gain(attribute_list, records_df)
        if len(info_gain):
            return max(info_gain, key=info_gain.get)
        return None


class InformationRatioTree(Tree):
    def get_next_attribute(self, attribute_list, records_df):
        """Returns the attribute with the highest information gain ratio"""
        info_gain = information_gain(attribute_list, records_df)
        info_gain_ratio = dict()
        for attribute in attribute_list:
            p = records_df[attribute].value_counts() / len(records_df)
            int_value = -np.sum(p * np.log2(p))
            info_gain_ratio[attribute] = info_gain[attribute] / int_value
        if len(info_gain_ratio):
            return max(info_gain_ratio, key=info_gain_ratio.get)
        return None


def calc_entropy(attribute_list, records_df):
    """Returns the entropy dictionary"""
    entropy = dict()
    for attribute in attribute_list:
        p = records_df[attribute].value_counts() / len(records_df)
        entropy[attribute] = -np.sum(p * np.log2(p))
    return entropy


def information_gain(attribute_list, records_df, goal=GOAL):
    """Returns a dictionary of the information gain"""
    goal_entropy = calc_entropy([goal], records_df)[goal]
    info_gain = dict()
    for attribute in attribute_list:
        remaining_entropy = 0
        for val in records_df[attribute].unique():
            relevant = records_df[records_df[attribute] == val]
            p = relevant[goal].value_counts() / len(relevant)
            remaining_entropy += -(np.sum(p * np.log2(p) * len(relevant)) / len(records_df))
        info_gain[attribute] = goal_entropy - remaining_entropy
    return info_gain
