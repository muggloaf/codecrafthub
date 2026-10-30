# Final project submission snippets

These snippets are implemented in `index.html`.

## Question 1 — updated title tag

```html
<title>CodeCraftHub: Your Learning Management Platform</title>
```

## Question 2 — updated .btn-primary styling

```css
.btn-primary {
  background-color: #8B5CF6;
  color: #FFFFFF;
}
```

## Question 3 — updated .btn-success styling

```css
.btn-success {
  background-color: #F59E0B;
  color: #111827;
}
```

## Question 4 — updated delete button code

This line is inside the course-row JavaScript template literal. The numeric
`${course.id}` is replaced by each course's actual backend-generated ID.

```html
<button type="button" class="btn btn-danger" onclick="deleteCourse(${course.id})">Remove</button>
```

Its class applies the requested red background:

```css
.btn-danger { background-color: #EF4444; color: #FFFFFF; }
```
