import React from 'react';
import { connect } from 'react-redux'
import * as analyzejson from './analyzejson'
import { bindActionCreators } from 'redux'
import {
  Header,
  Grid,
  List,
  Form,
  Button,
  Input
} from 'semantic-ui-react'

var styleheight2 = {
  minHeight:"175px",
}

var stylefloat = {
  // float: "left",
  marginTop: "10px",
  width: "55%"
}

var stylefloat1 = {
  float: "right",
  marginTop: "10px",
  width: "55%"
}

var styleboder = {
  border: "solid 1px",
  color: "rgb(229, 229, 229)"
}

let backstyle = {
  backgroundColor: "#e5e5e5"
}

class Attributes extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      fields: ['text', 'dataField', 'type'],
      selected: 0,
      text: '',
      dataField: '',
      type: '',
      collecitonkey: 0,
    }
    this.handleOnchange = this.handleOnchange.bind(this)
    this.handleformsubmit = this.handleformsubmit.bind(this)
  }

  handleselect(index) {
    this.state.fields.map((key, index) => {
      this.state[key] = ''
      return true
    })
    this.setState({
      selected: index
    })
  }

  handleOnchange(e) {
    this.state[e.target.placeholder] = e.target.value
    const value = e.target.value
    this.setState({place: value})
  }

  getcollectionname(key_index) {
    let rlt = ''
    Object.keys(this.props.json).map(function(key, index) {
      if (index === key_index) {
        rlt = key
      }
      return true
    })
    return rlt
  }

  getattributesname(key_index) {
    let rlt = ''
    Object.keys(this.props.json).map(function(key, index) {
      if (index === this.props.index) {
        rlt = this.props.json[key]['attributes'][key_index]
      }
      return true
    }, this)
    return rlt
  }

  handleformsubmit(e) {
    e.preventDefault()
    let data = {
      collectionId: this.getcollectionname(this.props.index),
      attributesId: this.getattributesname(this.state.selected),
      text: this.state.text,
      dataField: this.state.dataField,
      type: this.state.type,
    }
    this.props.analyze.change_attributes(data)
  }

  render() {
    let KEY = ''
    let attr = []
    let formdata = []
    if (this.state.collecitonkey !== this.props.index) {
      this.setState({collecitonkey: this.props.index})
      this.state.fields.map((key, index) => {
        this.state[key] = ''
        return true
      })
      this.state.selected = 0
    }
    if (Object.keys(this.props.json).length !== 0) {
      Object.keys(this.props.json).map(function(key, index) {
        if (index === this.props.index) {
          KEY = key
        }
        return true
      },this)
      attr = this.props.json[KEY]['attributes']

      const val = this.props.json[KEY]['attributes'][this.state.selected]
      formdata = this.props.json[KEY]['attributes'][val]
      Object.keys(formdata).map(function(key, index) {
        if (this.state[key] === '') this.state[key] = formdata[key]
        return true
      },this)
    }
    return (
      <div>
        <Header as='h4'>Attributes</Header>
        <Grid divided style={styleboder}>
            <Grid.Column width={6} style={styleheight2}>
              <List divided selection>
                {
                  attr.map((Item, index) => {
                    let cons = {}
                    if (index === this.state.selected) cons = backstyle
                    return(
                      <List.Item key={index} value='index' style={cons} onClick={() => this.handleselect(index)}>
                        <List.Content>{Item}</List.Content>
                      </List.Item>
                    )
                  })
                }
                </List>
            </Grid.Column>
            <Grid.Column width={10}>
              <Form widths='equal' onSubmit={this.handleformsubmit}>
                {this.state.fields.map((item, index) => {
                  return(
                    <div key={index}>
                      <Input 
                        label={item}
                        style={stylefloat}
                        placeholder={item}
                        value={this.state[item]}
                        onChange={this.handleOnchange}
                      />
                    </div>
                  )
                })}
                <Button disabled={Object.keys(this.props.json).length !== 0?false:true} type='submit' style={stylefloat1}>Change config</Button>
              </Form>
            </Grid.Column>
        </Grid>
      </div>
    )
  }
}

const mapStateToProps = (state) => ({
  json: state.configReducer
})

const mapDispatchToProps = dispatch => ({
  analyze: bindActionCreators(analyzejson, dispatch)
})

export default connect(mapStateToProps, mapDispatchToProps)(Attributes)