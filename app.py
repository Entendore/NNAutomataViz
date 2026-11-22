import sys
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, 
                               QHBoxLayout, QVBoxLayout, QLabel, QPushButton, 
                               QComboBox, QGroupBox)
from PySide6.QtCore import Qt, QPointF, QTimer, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath

class AnimatedAutomataWidget(QWidget):
    def __init__(self, title, config, parent=None):
        super().__init__(parent)
        self.title = title
        self.config = config
        
        # Animation state
        self.animating = False
        self.active_dots = []  # List of {x, y, target_x, target_y, progress, opacity, state}
        self.current_string = ""
        self.current_step = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.step_animation)
        
        self.setMinimumSize(450, 400)

    def start_animation(self, input_string):
        if self.animating:
            return
            
        self.current_string = input_string
        self.current_step = 0
        self.active_dots = []
        self.animating = True
        
        # Initialize starting dot(s)
        start_state = self.config['start_state']
        sx, sy = self.config['nodes'][start_state]
        self.active_dots.append({
            'x': sx, 'y': sy, 'state': start_state, 'opacity': 1.0
        })
        
        self.timer.start(400)  # Animation speed (ms per character)
        self.update()

    def step_animation(self):
        if self.current_step >= len(self.current_string):
            self.timer.stop()
            self.animating = False
            self.update()
            return
            
        char = self.current_string[self.current_step]
        new_dots = []
        
        for dot in self.active_dots:
            current_state = dot['state']
            # Look up transitions
            transitions = self.config['transitions'].get((current_state, char), [])
            
            for next_state in transitions:
                nx, ny = self.config['nodes'][next_state]
                new_dots.append({
                    'x': dot['x'], 'y': dot['y'],
                    'target_x': nx, 'target_y': ny,
                    'progress': 0.0,
                    'state': next_state, 
                    'opacity': 1.0 if len(transitions) == 1 else 0.8 # Slight transparency for NFA splits
                })
                
        self.active_dots = new_dots
        
        # Animate the movement smoothly (sub-ticks)
        self.anim_tick_counter = 0
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.sub_tick)
        self.anim_timer.start(20)
        
        self.current_step += 1

    def sub_tick(self):
        self.anim_tick_counter += 1
        all_done = True
        
        for dot in self.active_dots:
            if dot.get('progress', 1.0) < 1.0:
                dot['progress'] += 0.2
                if dot['progress'] > 1.0: dot['progress'] = 1.0
                
                # Interpolate position
                t = dot['progress']
                dot['x'] = dot['x'] + (dot['target_x'] - dot['x']) * t
                dot['y'] = dot['y'] + (dot['target_y'] - dot['y']) * t
                
                if dot['progress'] < 1.0:
                    all_done = False
                    
        self.update()
        
        if all_done or self.anim_tick_counter > 10:
            self.anim_timer.stop()
            # Snap to exact node positions to avoid drift
            for dot in self.active_dots:
                nx, ny = self.config['nodes'][dot['state']]
                dot['x'], dot['y'] = nx, ny

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw Title and String Info
        painter.setPen(QPen(Qt.black))
        font = QFont("Arial", 11, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QPointF(10, 20), self.title)
        
        # Draw Input String progress
        font = QFont("Courier", 12, QFont.Bold)
        painter.setFont(font)
        text_x = 20
        text_y = 45
        for i, char in enumerate(self.current_string):
            if i < self.current_step:
                painter.setPen(QPen(Qt.gray)) # Processed
            elif i == self.current_step and self.animating:
                painter.setPen(QPen(QColor("#E74C3C"))) # Current
            else:
                painter.setPen(QPen(Qt.black)) # Pending
            painter.drawText(QPointF(text_x, text_y), char)
            text_x += 15

        # Draw Edges
        for (from_id, to_id, label, style, is_loop) in self.config['edges']:
            pen = QPen(Qt.lightGray, 2, style)
            painter.setPen(pen)
            x1, y1 = self.config['nodes'][from_id]
            x2, y2 = self.config['nodes'][to_id]
            
            if is_loop:
                self.draw_self_loop(painter, x1, y1, label)
            else:
                self.draw_arrow(painter, x1, y1, x2, y2, label, Qt.lightGray)

        # Draw Nodes
        for node_id, (x, y) in self.config['nodes'].items():
            color = QColor("#E8E8E8")
            # Highlight active states
            for dot in self.active_dots:
                if dot['state'] == node_id and dot.get('progress', 1.0) >= 0.8:
                    color = QColor("#F5B041") # Active state color
            
            painter.setPen(QPen(Qt.darkGray, 2))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x, y), 22, 22)
            
            painter.setPen(QPen(Qt.black))
            font = QFont("Arial", 9, QFont.Bold)
            painter.setFont(font)
            text_rect = painter.fontMetrics().boundingRect(node_id)
            painter.drawText(QPointF(x - text_rect.width()/2, y + text_rect.height()/4), node_id)

        # Draw Animated Dots (The "Data" flowing through)
        for dot in self.active_dots:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#2E86C1"))) # Blue data token
            painter.setOpacity(dot.get('opacity', 1.0))
            painter.drawEllipse(QPointF(dot['x'], dot['y']), 8, 8)
            
        painter.setOpacity(1.0)
        painter.end()

    def draw_arrow(self, painter, x1, y1, x2, y2, label, color):
        angle = math.atan2(y2 - y1, x2 - x1)
        dx, dy = 22 * math.cos(angle), 22 * math.sin(angle)
        sx, sy = x1 + dx, y1 + dy
        ex, ey = x2 - dx, y2 - dy

        path = QPainterPath(QPointF(sx, sy))
        path.lineTo(QPointF(ex, ey))
        painter.drawPath(path)

        arrow_size = 8
        p1 = QPointF(ex - arrow_size * math.cos(angle - math.pi/6), ey - arrow_size * math.sin(angle - math.pi/6))
        p2 = QPointF(ex - arrow_size * math.cos(angle + math.pi/6), ey - arrow_size * math.sin(angle + math.pi/6))
        arrow_head = QPainterPath(QPointF(ex, ey))
        arrow_head.lineTo(p1)
        arrow_head.lineTo(p2)
        arrow_head.closeSubpath()
        painter.fillPath(arrow_head, QBrush(color))

        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        painter.setPen(QPen(Qt.gray))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(QPointF(mid_x, mid_y - 5), label)

    def draw_self_loop(self, painter, x, y, label):
        path = QPainterPath(QPointF(x, y - 22))
        path.cubicTo(QPointF(x - 35, y - 70), QPointF(x + 35, y - 70), QPointF(x, y - 22))
        painter.drawPath(path)
        painter.setPen(QPen(Qt.gray))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(QPointF(x - 8, y - 55), label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NN Architectures ↔ Automata: String Processing Animation")
        self.resize(1000, 600)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.setup_fnn_tab()
        self.setup_rnn_tab()
        self.setup_transformer_tab()

    def create_tab_layout(self, group_title, small_config, large_config, strings):
        layout = QHBoxLayout()
        
        # Small Model Group
        small_box = QGroupBox(f"Small Model (Few Params - {group_title})")
        small_layout = QVBoxLayout()
        self.small_widget = AnimatedAutomataWidget("Topology", small_config)
        small_layout.addWidget(self.small_widget)
        
        ctrl_layout = QHBoxLayout()
        small_combo = QComboBox()
        small_combo.addItems(strings)
        small_btn = QPushButton("Run String")
        ctrl_layout.addWidget(small_combo)
        ctrl_layout.addWidget(small_btn)
        small_layout.addLayout(ctrl_layout)
        small_box.setLayout(small_layout)
        
        small_btn.clicked.connect(lambda: self.small_widget.start_animation(small_combo.currentText()))

        # Large Model Group
        large_box = QGroupBox(f"Large Model (Many Params - {group_title})")
        large_layout = QVBoxLayout()
        self.large_widget = AnimatedAutomataWidget("Topology", large_config)
        large_layout.addWidget(self.large_widget)
        
        ctrl_layout2 = QHBoxLayout()
        large_combo = QComboBox()
        large_combo.addItems(strings)
        large_btn = QPushButton("Run String")
        ctrl_layout2.addWidget(large_combo)
        ctrl_layout2.addWidget(large_btn)
        large_layout.addLayout(ctrl_layout2)
        large_box.setLayout(large_layout)
        
        large_btn.clicked.connect(lambda: self.large_widget.start_animation(large_combo.currentText()))

        layout.addWidget(small_box, 1)
        layout.addWidget(large_box, 1)
        
        container = QWidget()
        container.setLayout(layout)
        return container

    def setup_fnn_tab(self):
        # Small FNN: Only 1 hidden layer (Acyclic)
        small_nodes = {'I': (50, 150), 'H': (200, 150), 'O': (350, 150)}
        small_edges = [('I', 'H', 'W1', Qt.SolidLine, False), ('H', 'O', 'W2', Qt.SolidLine, False)]
        small_trans = {('I', '0'): ['H'], ('I', '1'): ['H'], ('H', '0'): ['O'], ('H', '1'): ['O']}
        small_config = {'nodes': small_nodes, 'edges': small_edges, 'transitions': small_trans, 'start_state': 'I'}

        # Large FNN: 3 hidden layers (Deeper parameters)
        large_nodes = {'I': (50, 150), 'H1': (150, 100), 'H2': (250, 150), 'H3': (150, 200), 'O': (350, 150)}
        large_edges = [
            ('I', 'H1', 'W1', Qt.SolidLine, False), ('I', 'H3', 'W1', Qt.SolidLine, False),
            ('H1', 'H2', 'W2', Qt.SolidLine, False), ('H3', 'H2', 'W2', Qt.SolidLine, False),
            ('H2', 'O', 'W3', Qt.SolidLine, False)
        ]
        large_trans = {
            ('I', '0'): ['H1', 'H3'], ('I', '1'): ['H1', 'H3'], 
            ('H1', '0'): ['H2'], ('H1', '1'): ['H2'], ('H3', '0'): ['H2'], ('H3', '1'): ['H2'],
            ('H2', '0'): ['O'], ('H2', '1'): ['O']
        }
        large_config = {'nodes': large_nodes, 'edges': large_edges, 'transitions': large_trans, 'start_state': 'I'}

        strings = ["0", "1", "01", "10", "11"]
        self.tabs.addTab(self.create_tab_layout("Acyclic DFA (FNN)", small_config, large_config, strings), "FNN ↔ Acyclic DFA")

    def setup_rnn_tab(self):
        # Small RNN: Simple hidden state
        small_nodes = {'I': (50, 200), 'H': (200, 150), 'O': (350, 200)}
        small_edges = [('I', 'H', 'W_xh', Qt.SolidLine, False), ('H', 'O', 'W_hy', Qt.SolidLine, False), ('H', 'H', 'W_hh', Qt.DashLine, True)]
        small_trans = {
            ('I', '0'): ['H'], ('I', '1'): ['H'], 
            ('H', '0'): ['H'], ('H', '1'): ['H'] # Stays in hidden
        }
        small_config = {'nodes': small_nodes, 'edges': small_edges, 'transitions': small_trans, 'start_state': 'I'}

        # Large RNN: LSTM-style (Memory + Hidden split)
        large_nodes = {'I': (50, 150), 'C': (200, 80), 'H': (200, 220), 'O': (350, 150)}
        large_edges = [
            ('I', 'H', 'W_xh', Qt.SolidLine, False), ('H', 'O', 'W_hy', Qt.SolidLine, False), 
            ('H', 'H', 'Recurrence', Qt.DashLine, True), ('C', 'C', 'Cell State', Qt.SolidLine, True),
            ('H', 'C', 'Forget Gate', Qt.DotLine, False), ('C', 'H', 'Out Gate', Qt.DotLine, False)
        ]
        large_trans = {
            ('I', '0'): ['H'], ('I', '1'): ['H'], 
            ('H', '0'): ['H'], ('H', '1'): ['H'],
            ('C', '0'): ['C'], ('C', '1'): ['C']
        }
        large_config = {'nodes': large_nodes, 'edges': large_edges, 'transitions': large_trans, 'start_state': 'I'}

        strings = ["0101", "111", "00110", "000"]
        self.tabs.addTab(self.create_tab_layout("Cyclic DFA (RNN/LSTM)", small_config, large_config, strings), "RNN ↔ Cyclic DFA")

    def setup_transformer_tab(self):
        # Transformer: NFA (Attention splits paths)
        # String reads 'a' or 'b'. If reads 'b', nondeterministically jumps to future context
        small_nodes = {'I': (50, 150), 'Q': (200, 150), 'O': (350, 150)}
        small_edges = [('I', 'Q', 'K/V', Qt.SolidLine, False), ('Q', 'O', 'FFN', Qt.SolidLine, False)]
        small_trans = {('I', 'a'): ['Q'], ('I', 'b'): ['Q'], ('Q', 'a'): ['O'], ('Q', 'b'): ['O']}
        small_config = {'nodes': small_nodes, 'edges': small_edges, 'transitions': small_trans, 'start_state': 'I'}

        large_nodes = {'I': (50, 150), 'Q1': (200, 80), 'Q2': (200, 220), 'O': (350, 150)}
        large_edges = [
            ('I', 'Q1', 'Head 1', Qt.SolidLine, False), ('I', 'Q2', 'Head 2', Qt.SolidLine, False),
            ('Q1', 'O', 'FFN', Qt.SolidLine, False), ('Q2', 'O', 'FFN', Qt.SolidLine, False)
        ]
        # NFA: 'b' splits into multiple attention paths (Multi-head attention branching)
        large_trans = {
            ('I', 'a'): ['Q1'], 
            ('I', 'b'): ['Q1', 'Q2'],  # Nondeterministic split!
            ('Q1', 'a'): ['O'], ('Q1', 'b'): ['O'], 
            ('Q2', 'a'): ['O'], ('Q2', 'b'): ['O']
        }
        large_config = {'nodes': large_nodes, 'edges': large_edges, 'transitions': large_trans, 'start_state': 'I'}

        strings = ["a", "b", "aba", "abb", "bab"]
        self.tabs.addTab(self.create_tab_layout("NFA (Transformer Attention)", small_config, large_config, strings), "Transformer ↔ NFA")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())