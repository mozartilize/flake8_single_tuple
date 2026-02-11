use pyo3::prelude::*;

#[pyclass]
struct Scanner {
    source: String,
    line_offsets: Vec<usize>,
}

#[derive(FromPyObject)]
struct NodeCoords {
    id: usize,
    lineno: usize,
    col_offset: usize,
    end_lineno: usize,
    end_col_offset: usize,
    is_call_arg: bool,
    is_comp_or_assign: bool,
}

#[pymethods]
impl Scanner {
    #[new]
    fn new(source: String) -> Self {
        let mut line_offsets = vec![0];
        let mut offset = 0;
        for line in source.split_inclusive('\n') {
            offset += line.len();
            line_offsets.push(offset);
        }
        Scanner { source, line_offsets }
    }

    fn check_nodes(&self, nodes: Vec<NodeCoords>) -> Vec<usize> {
        let bytes = self.source.as_bytes();
        let mut violations = Vec::new();

        for node in nodes {
            let start = self.get_offset(node.lineno, node.col_offset);
            let end = self.get_offset(node.end_lineno, node.end_col_offset);

            if self.is_violation(start, end, node.is_call_arg, node.is_comp_or_assign, bytes) {
                violations.push(node.id);
            }
        }
        violations
    }

    fn get_offset(&self, lineno: usize, col: usize) -> usize {
        self.line_offsets.get(lineno - 1).copied().unwrap_or(0) + col
    }

    fn is_violation(&self, start: usize, end: usize, is_call_arg: bool, is_comp_or_assign: bool, bytes: &[u8]) -> bool {
        let mut left = start as i32 - 1;
        while left >= 0 && (bytes[left as usize] as char).is_whitespace() {
            left -= 1;
        }

        let mut right = end;
        while right < bytes.len() && (bytes[right] as char).is_whitespace() {
            right += 1;
        }

        if left >= 0 && right < bytes.len() && bytes[left as usize] == b'(' && bytes[right] == b')' {
            if is_comp_or_assign {
                return !self.has_comma_in_span(left as usize, right + 1);
            }
            if is_call_arg {
                let mut o_left = left - 1;
                while o_left >= 0 && (bytes[o_left as usize] as char).is_whitespace() {
                    o_left -= 1;
                }
                let mut o_right = right + 1;
                while o_right < bytes.len() && (bytes[o_right] as char).is_whitespace() {
                    o_right += 1;
                }
                if o_left >= 0 && o_right < bytes.len() && bytes[o_left as usize] == b'(' && bytes[o_right] == b')' {
                    return !self.has_comma_in_span(left as usize, right + 1);
                }
            }
        }
        false
    }

    fn has_comma_in_span(&self, start: usize, end: usize) -> bool {
        self.source.get(start..end).map_or(false, |s| s.contains(','))
    }
}

/// Fixed for PyO3 0.20: Removed Bound and used &PyModule
#[pymodule]
fn rust_tuple_scanner(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Scanner>()?;
    Ok(())
}